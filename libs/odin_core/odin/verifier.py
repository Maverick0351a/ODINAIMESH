from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union
import os
import time

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # noqa: F401

from .jwks import KeyRegistry
from .oml import compute_cid, to_oml_c
from .ope import verify_over_content


@dataclass
class VerifyResult:
    ok: bool
    reason: Optional[str] = None
    kid: Optional[str] = None
    cid: Optional[str] = None
    used_jwks: bool = False


def _b64url_to_json(s: str) -> Dict[str, Any]:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    raw = base64.urlsafe_b64decode(s + pad)
    return json.loads(raw.decode("utf-8"))


def _load_jwks(jwks: Optional[Union[Dict[str, Any], str]]) -> Optional[Dict[str, Any]]:
    if jwks is None:
        return None
    if isinstance(jwks, dict):
        return jwks
    src = jwks.strip()
    if src.startswith("http://") or src.startswith("https://"):
        if httpx is None:
            raise RuntimeError("httpx not available for JWKS URL fetch")
    r = httpx.get(src, timeout=5.0)
    r.raise_for_status()
    return r.json()
    # Treat as JSON string or path to file
    try:
        # Try parse as JSON inline
        return json.loads(src)
    except Exception:
        pass
    # Try path
    with open(src, "r", encoding="utf-8") as f:
        return json.load(f)


# --- JWKS caching & rotation grace ------------------------------------------

# Cache the most recent JWKS fetched per URL, with a previous snapshot retained
# for a short grace window after rotation.
_JWKS_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
_JWKS_PREV: Dict[str, Tuple[Dict[str, Any], float]] = {}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _now() -> float:
    return time.time()


def _fetch_jwks_url_with_cache(url: str) -> Dict[str, Any]:
    ttl = _env_int("JWKS_CACHE_TTL", 300)
    now = _now()
    cur = _JWKS_CACHE.get(url)
    if cur is not None:
        jwks_doc, ts = cur
        if ttl <= 0 or now - ts < ttl:
            return jwks_doc
    # Fetch fresh
    if httpx is None:
        raise RuntimeError("httpx not available for JWKS URL fetch")
    r = httpx.get(url, timeout=5.0)
    r.raise_for_status()
    fresh = r.json()
    # If changed, move current to prev with timestamp
    if cur is not None:
        prev_doc, prev_ts = cur
        try:
            if json.dumps(prev_doc, sort_keys=True) != json.dumps(fresh, sort_keys=True):
                _JWKS_PREV[url] = (prev_doc, prev_ts)
        except Exception:
            # If comparison fails, still keep previous
            _JWKS_PREV[url] = (prev_doc, prev_ts)
    _JWKS_CACHE[url] = (fresh, now)
    return fresh


def _keys_iter(jwks: Dict[str, Any]):
    try:
        for k in jwks.get("keys", []) or []:
            yield k
    except Exception:
        return


def _kid_in_jwks(jwks: Dict[str, Any], kid: str) -> Optional[str]:
    for k in _keys_iter(jwks):
        if k.get("kid") == kid and k.get("kty") == "OKP" and k.get("crv") == "Ed25519":
            x = k.get("x")
            if isinstance(x, str) and x:
                return x
    return None


def _resolve_kid_pub_b64u(jwks_source: Union[Dict[str, Any], str], kid: str) -> Optional[Tuple[str, bool]]:
    """
    Resolve the Ed25519 public key (JWK 'x' b64url) for kid from the provided JWKS source.
    Returns tuple (x_b64u, used_grace) or None if not found (including after grace).
    Applies caching for URL sources with TTL and honors rotation grace by falling
    back to the previously cached JWKS within ROTATION_GRACE_SEC seconds.
    """
    # Inline dict: just search
    if isinstance(jwks_source, dict):
        x = _kid_in_jwks(jwks_source, kid)
        return (x, False) if x else None

    # String: could be URL, inline JSON, or path
    src = jwks_source.strip()
    if src.startswith("http://") or src.startswith("https://"):
        current = _fetch_jwks_url_with_cache(src)
        x = _kid_in_jwks(current, kid)
        if x:
            return (x, False)
        # Not in current; check previous within grace
        grace = _env_int("ROTATION_GRACE_SEC", 600)
        prev = _JWKS_PREV.get(src)
        if prev is not None:
            prev_doc, ts = prev
            if grace > 0 and (_now() - ts) <= grace:
                x_prev = _kid_in_jwks(prev_doc, kid)
                if x_prev:
                    return (x_prev, True)
        return None

    # Non-URL string: attempt to load and search (no caching)
    jwks_dict = _load_jwks(src)
    if jwks_dict is None:
        return None
    x = _kid_in_jwks(jwks_dict, kid)
    return (x, False) if x else None


def _jwks_kid_to_x_b64u(jwks: Dict[str, Any], kid: str) -> Optional[str]:
    try:
        keys = jwks.get("keys", [])
        for k in keys:
            if k.get("kid") == kid and k.get("kty") == "OKP" and k.get("crv") == "Ed25519":
                x = k.get("x")
                if isinstance(x, str) and x:
                    return x
    except Exception:
        return None
    return None


def verify(
    *,
    oml_c_bytes: Optional[bytes] = None,
    oml_c_path: Optional[str] = None,
    oml_c_obj: Optional[Any] = None,
    receipt: Optional[Dict[str, Any]] = None,
    envelope: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    expected_cid: Optional[str] = None,
    jwks: Optional[Union[Dict[str, Any], str]] = None,
) -> VerifyResult:
    """
    Flexible verification:
    - Provide OML-C via bytes or path, paired with OPE (from receipt or headers)
    - Or supply a full receipt JSON (with embedded OPE and either path or inline bytes)
    - Optionally enforce expected CID and/or JWKS kid resolution
    """
    try:
        ope: Optional[Dict[str, Any]] = None
        cid_from_input: Optional[str] = None
        jwks_source: Optional[Union[Dict[str, Any], str]] = jwks

        # Source precedence: receipt > headers > (oml_c_* + explicit ope not supported here)
        if receipt is not None:
            ope = receipt.get("ope") if isinstance(receipt.get("ope"), dict) else receipt
            cid_from_input = receipt.get("oml_cid") or receipt.get("cid")
            if oml_c_bytes is None and oml_c_path is None:
                if isinstance(receipt.get("oml_c_b64"), str):
                    oml_c_bytes = base64.b64decode(receipt["oml_c_b64"] + "==")
                elif isinstance(receipt.get("oml_c_path"), str):
                    oml_c_path = receipt["oml_c_path"]
        # Envelope support: 'ope' is base64url-encoded OPE JSON; may include inline OML-C and JWKS
        if ope is None and envelope is not None:
            if isinstance(envelope.get("ope"), str):
                try:
                    ope = _b64url_to_json(envelope["ope"])  # decode to OPE JSON dict
                except Exception:
                    return VerifyResult(ok=False, reason="invalid_envelope_ope")
            cid_from_input = envelope.get("oml_cid") or cid_from_input
            if oml_c_bytes is None and oml_c_path is None:
                if isinstance(envelope.get("oml_c_b64"), str):
                    oml_c_bytes = base64.urlsafe_b64decode(envelope["oml_c_b64"] + "==")
                elif isinstance(envelope.get("oml_c_path"), str):
                    oml_c_path = envelope["oml_c_path"]
            # Prefer explicit jwks param; else use envelope-provided inline/url
            if jwks_source is None:
                if isinstance(envelope.get("jwks_inline"), dict):
                    jwks_source = envelope["jwks_inline"]
                elif isinstance(envelope.get("jwks_url"), str):
                    jwks_source = envelope["jwks_url"]
        if ope is None and headers is not None:
            if isinstance(headers.get("X-ODIN-OPE"), str):
                try:
                    ope = _b64url_to_json(headers["X-ODIN-OPE"])
                except Exception:
                    return VerifyResult(ok=False, reason="invalid_header_ope")
            cid_from_input = headers.get("X-ODIN-OML-CID") or cid_from_input
            if oml_c_bytes is None and oml_c_path is None:
                p = headers.get("X-ODIN-OML-C-Path")
                if p:
                    oml_c_path = p

        if ope is None:
            return VerifyResult(ok=False, reason="missing_ope")

        # Load content bytes
        if oml_c_bytes is None:
            if oml_c_obj is not None:
                # Encode object to OML-C using default SFT
                oml_c_bytes = to_oml_c(oml_c_obj)
            elif oml_c_path is not None:
                with open(oml_c_path, "rb") as f:
                    oml_c_bytes = f.read()
            else:
                return VerifyResult(ok=False, reason="missing_oml_c")

        # Compute CID and compare against provided/claimed CID (if any)
        cid = compute_cid(oml_c_bytes)
        expected = expected_cid or cid_from_input
        if expected is not None and cid != expected:
            return VerifyResult(ok=False, reason="cid_mismatch", cid=cid)

        # If OPE itself declares an oml_cid, it must match computed CID
        ope_oml_cid = ope.get("oml_cid") if isinstance(ope, dict) else None
        if isinstance(ope_oml_cid, str) and ope_oml_cid and ope_oml_cid != cid:
            return VerifyResult(ok=False, reason="oml_cid_mismatch", cid=cid)

        # Verify with embedded pub
        # Only enforce expected_oml_cid check if OPE declared a CID; otherwise rely on hash + signature
        expected_for_verify = ope_oml_cid if isinstance(ope_oml_cid, str) and ope_oml_cid else None
        res = verify_over_content(ope, oml_c_bytes, expected_oml_cid=expected_for_verify)
        if not res.get("ok"):
            return VerifyResult(ok=False, reason=res.get("reason") or "verify_failed", cid=cid)

        # Optional JWKS kid resolution
        used_jwks = False
        if jwks_source is not None:
            kid = ope.get("kid")
            if not kid:
                return VerifyResult(ok=False, reason="missing_kid_for_jwks", cid=cid)
            resolved = _resolve_kid_pub_b64u(jwks_source, kid)
            if not resolved:
                return VerifyResult(ok=False, reason="kid_not_in_jwks", cid=cid)
            x, _used_grace = resolved
            # Cross-check embedded pub matches JWKS x
            if ope.get("pub_b64u") != x:
                # As a stricter check, re-run verification forcing the JWKS key
                ope_jwks = dict(ope)
                ope_jwks["pub_b64u"] = x
                res2 = verify_over_content(ope_jwks, oml_c_bytes, expected_oml_cid=expected)
                if not res2.get("ok"):
                    return VerifyResult(ok=False, reason="jwks_pub_mismatch", cid=cid)
            used_jwks = True

        return VerifyResult(ok=True, kid=res.get("kid"), cid=cid, used_jwks=used_jwks)
    except Exception as e:  # pragma: no cover (defensive)
        return VerifyResult(ok=False, reason=f"error:{type(e).__name__}:{e}")


__all__ = ["VerifyResult", "verify"]
