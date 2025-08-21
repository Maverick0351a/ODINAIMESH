import base64
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .constants import (
    ENV_JWKS_JSON,
    ENV_JWKS_PATH,
    ENV_SINGLE_PUBKEY,
    ENV_SINGLE_PUBKEY_KID,
)


# --- helpers -----------------------------------------------------------------

def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_to_bytes(s: str) -> bytes:
    # Accept base64url with or without padding
    s = s.strip()
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _maybe_hex_to_bytes(s: str) -> Optional[bytes]:
    st = s.strip().lower()
    if st.startswith("0x"):
        st = st[2:]
    if all(c in "0123456789abcdef" for c in st) and len(st) % 2 == 0:
        try:
            return bytes.fromhex(st)
        except ValueError:
            return None
    return None


def _maybe_b64_to_bytes(s: str) -> Optional[bytes]:
    # Try forgiving decode: treat '+'/'/' as standard base64; '-'/'_' as urlsafe
    s = s.strip()
    try:
        # Try urlsafe first
        return _b64url_to_bytes(s)
    except Exception:
        pass
    try:
        # Fallback to standard base64
        pad = "=" * ((4 - (len(s) % 4)) % 4)
        return base64.b64decode(s + pad)
    except Exception:
        return None


def _normalize_pubkey_x(s: str) -> str:
    """
    Normalize a provided Ed25519 public key into JWK 'x' (base64url w/o padding).
    Accepts raw hex, base64, or base64url. Enforces 32-byte length.
    """
    b = _maybe_hex_to_bytes(s)
    if b is None:
        b = _maybe_b64_to_bytes(s)
    if b is None:
        raise ValueError("ODIN_OPE_PUBKEY must be hex, base64, or base64url")
    if len(b) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes; got {len(b)}")
    return _b64url_nopad(b)


# --- core --------------------------------------------------------------------


@dataclass(frozen=True)
class JWK:
    kty: str
    crv: str
    x: str
    kid: Optional[str] = None
    alg: str = "EdDSA"
    use: Optional[str] = "sig"

    def to_dict(self) -> Dict[str, str]:
        d = {"kty": self.kty, "crv": self.crv, "x": self.x, "alg": self.alg}
        if self.use:
            d["use"] = self.use
        if self.kid:
            d["kid"] = self.kid
        return d


class KeyRegistry:
    """
    Minimal, production-grade JWKS provider for ODIN Gateway.
    Precedence:
      1) ODIN_OPE_JWKS           (inline JSON string)
      2) ODIN_OPE_JWKS_PATH      (path to JSON file)
      3) ODIN_OPE_PUBKEY (+ ODIN_OPE_KID)  (single Ed25519 key)
    """

    def __init__(self, keys: List[JWK]):
        self._keys = keys

    @classmethod
    def from_env(cls) -> "KeyRegistry":
        # 1) Inline JWKS JSON
        jwks_inline = (os.getenv(ENV_JWKS_JSON) or "").strip()
        if jwks_inline:
            try:
                data = json.loads(jwks_inline)
                keys = cls._parse_jwks(data)
                return cls(keys)
            except Exception as e:
                raise ValueError(f"{ENV_JWKS_JSON} is invalid: {e}")

        # 2) JWKS file path
        jwks_path = (os.getenv(ENV_JWKS_PATH) or "").strip()
        if jwks_path:
            try:
                with open(jwks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                keys = cls._parse_jwks(data)
                return cls(keys)
            except Exception as e:
                raise ValueError(f"{ENV_JWKS_PATH}={jwks_path} is invalid: {e}")

        # 3) Single pubkey via env
        single_key = (os.getenv(ENV_SINGLE_PUBKEY) or "").strip()
        if single_key:
            kid = (os.getenv(ENV_SINGLE_PUBKEY_KID) or "env:default").strip() or "env:default"
            x = _normalize_pubkey_x(single_key)
            jwk = JWK(kty="OKP", crv="Ed25519", x=x, kid=kid)
            return cls([jwk])

        # Nothing configured -> empty set (served as {"keys":[]})
        return cls([])

    @staticmethod
    def _parse_jwks(data: Dict) -> List[JWK]:
        if not isinstance(data, dict) or "keys" not in data or not isinstance(data["keys"], list):
            raise ValueError("JWKS must be an object with a 'keys' array")
        out: List[JWK] = []
        for i, k in enumerate(data["keys"]):
            if not isinstance(k, dict):
                raise ValueError(f"JWKS keys[{i}] must be an object")
            if k.get("kty") != "OKP" or k.get("crv") != "Ed25519":
                raise ValueError(f"JWKS keys[{i}] must be OKP/Ed25519")
            x = k.get("x")
            if not isinstance(x, str) or not x:
                raise ValueError(f"JWKS keys[{i}] missing 'x'")
            # Validate x is base64url for 32-byte key
            try:
                raw = _b64url_to_bytes(x)
            except Exception as e:
                raise ValueError(f"JWKS keys[{i}].x invalid base64url: {e}")
            if len(raw) != 32:
                raise ValueError(f"JWKS keys[{i}].x must decode to 32 bytes")
            out.append(
                JWK(
                    kty="OKP",
                    crv="Ed25519",
                    x=_b64url_nopad(raw),
                    kid=k.get("kid"),
                    alg=k.get("alg", "EdDSA"),
                    use=k.get("use", "sig"),
                )
            )
        # Ensure unique kids if provided and unique key material
        kids = [k.kid for k in out if k.kid]
        if len(kids) != len(set(kids)):
            raise ValueError("Duplicate 'kid' values in JWKS")
        xs = [k.x for k in out]
        if len(xs) != len(set(xs)):
            raise ValueError("Duplicate key material (x) in JWKS")
        return out

    def to_jwks(self) -> Dict[str, List[Dict[str, str]]]:
        # Return deterministic order by kid then x
        keys_sorted = sorted(self._keys, key=lambda j: ((j.kid or ""), j.x))
        return {"keys": [j.to_dict() for j in keys_sorted]}

    # Convenience for future verification plumbing
    def by_kid(self) -> Dict[str, JWK]:
        return {k.kid: k for k in self._keys if k.kid is not None}


__all__ = [
    "JWK",
    "KeyRegistry",
]
