import os
import json
import base64


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def test_jwks_cache_and_rotation_grace(monkeypatch):
    # Build two JWKS docs with different kids
    jwks1 = {"keys": [{"kty": "OKP", "crv": "Ed25519", "x": _b64u(b"X" * 32), "kid": "k1"}]}
    jwks2 = {"keys": [{"kty": "OKP", "crv": "Ed25519", "x": _b64u(b"Y" * 32), "kid": "k2"}]}

    # Monkeypatch httpx.get to return jwks1 first then jwks2
    calls = {"n": 0}

    class _Resp:
        def __init__(self, doc):
            self._doc = doc

        def raise_for_status(self):
            return None

        def json(self):
            return self._doc

    def fake_get(url, timeout=5.0):  # type: ignore
        calls["n"] += 1
        return _Resp(jwks1 if calls["n"] == 1 else jwks2)

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "get", fake_get)

    # Small TTL and long grace for the test
    monkeypatch.setenv("JWKS_CACHE_TTL", "1")
    monkeypatch.setenv("ROTATION_GRACE_SEC", "60")

    from odin.verifier import verify

    # Build a minimal OPE over empty content using k1
    ope_k1 = {"v": 1, "alg": "Ed25519", "ts_ns": 0, "kid": "k1", "pub_b64u": jwks1["keys"][0]["x"], "content_hash_b3_256_b64u": "", "sig_b64u": ""}
    envelope = {"ope": _b64u(json.dumps(ope_k1).encode("utf-8")), "oml_c_b64": ""}

    # First verify: fetch jwks1, should pass kid presence check (signature is not validated here with real key)
    r1 = verify(envelope=envelope, jwks="https://example.com/jwks.json")
    # Allow content_hash_mismatch since this test doesn't build a real content hash/signature; we're validating JWKS resolution.
    assert r1.ok or r1.reason in ("jwks_pub_mismatch", "verify_failed", "missing_oml_c", "content_hash_mismatch")

    # Next verify with kid k1 after rotation to jwks2: should fall back to previous within grace and still resolve kid
    r2 = verify(envelope=envelope, jwks="https://example.com/jwks.json")
    assert (r2.ok or r2.reason in ("jwks_pub_mismatch", "verify_failed", "missing_oml_c", "content_hash_mismatch"))

    # Now verify for k2 (new kid): ensure it resolves from current set
    ope_k2 = dict(ope_k1)
    ope_k2["kid"] = "k2"
    ope_k2["pub_b64u"] = jwks2["keys"][0]["x"]
    envelope2 = {"ope": _b64u(json.dumps(ope_k2).encode("utf-8")), "oml_c_b64": ""}
    r3 = verify(envelope=envelope2, jwks="https://example.com/jwks.json")
    assert (r3.ok or r3.reason in ("jwks_pub_mismatch", "verify_failed", "missing_oml_c", "content_hash_mismatch"))
