from __future__ import annotations

import json
from base64 import urlsafe_b64encode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from libs.odin_core.odin.http_sig import sign_v1, verify_v1


def _b64u(b: bytes) -> str:
    s = urlsafe_b64encode(b).decode("ascii")
    return s.rstrip("=")


def _jwks_from_priv(priv: Ed25519PrivateKey, kid: str):
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": kid, "x": _b64u(pub_bytes)}]}


def test_httpsig_roundtrip():
    priv = Ed25519PrivateKey.generate()
    kid = "k1"
    jwks = _jwks_from_priv(priv, kid)
    body = json.dumps({"x": 1}, separators=(",", ":")).encode("utf-8")
    path = "/task"
    hdr = sign_v1(method="POST", path=path, body=body, kid=kid, priv=priv)
    info = verify_v1(method="POST", path=path, body=body, header=hdr, jwks=jwks)
    assert info["ok"] and info["kid"] == kid
