import json
import base64
import httpx
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


@dataclass
class VerifyResult:
    ok: bool
    reason: Optional[str] = None
    kid: Optional[str] = None


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "==")


def _find_pub_from_jwks(jwks: dict, kid: str) -> Optional[bytes]:
    for k in jwks.get("keys", []):
        if k.get("kid") == kid and k.get("kty") == "OKP" and k.get("crv") == "Ed25519" and "x" in k:
            return _b64u_decode(k["x"])  # raw 32-byte public key
    return None


def verify_envelope(envelope: dict, jwks_url: str) -> VerifyResult:
    """Minimal OPE verify over inline content (oml_c_b64) using JWKS URL.
    Does not implement all gateway semantics; preview-only.
    """
    try:
        ope_b64 = envelope.get("ope")
        if not ope_b64:
            return VerifyResult(ok=False, reason="missing_ope")
        ope = json.loads(base64.b64decode(ope_b64).decode("utf-8"))
        kid = ope.get("kid")
        if not kid:
            return VerifyResult(ok=False, reason="missing_kid")
        oml_c_b64 = envelope.get("oml_c_b64")
        if not oml_c_b64:
            return VerifyResult(ok=False, reason="missing_oml_c")
        content = base64.b64decode(oml_c_b64)
        sig = base64.urlsafe_b64decode(ope.get("sig_b64u", "") + "==")
        # Fetch JWKS
        r = httpx.get(jwks_url, timeout=5.0)
        r.raise_for_status()
        jwks = r.json()
        pub = _find_pub_from_jwks(jwks, kid)
        if not pub:
            return VerifyResult(ok=False, reason="kid_not_found", kid=kid)
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, content)
        return VerifyResult(ok=True, kid=kid)
    except Exception as e:
        return VerifyResult(ok=False, reason=f"verify_failed:{type(e).__name__}")
