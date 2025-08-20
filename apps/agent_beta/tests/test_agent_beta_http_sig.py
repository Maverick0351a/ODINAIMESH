from __future__ import annotations

import json
from base64 import urlsafe_b64encode

from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from libs.odin_core.odin.http_sig import sign_v1


def _b64u(b: bytes) -> str:
    return urlsafe_b64encode(b).decode("ascii").rstrip("=")


def test_agent_beta_requires_signature(monkeypatch):
    # Start app
    from apps.agent_beta import api as beta_api

    client = TestClient(beta_api.app)

    # Enforce signatures
    monkeypatch.setenv("ODIN_HTTP_SIGN_REQUIRE", "1")

    # 1) Missing signature -> 401
    payload = {"intent": "beta.request", "task": "math.add", "args": {"a": 2, "b": 2}}
    r = client.post("/task", json=payload)
    assert r.status_code == 401

    # 2) Valid signature accepted
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    jwks = {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": "k1", "x": _b64u(pub)}]}
    monkeypatch.setenv("ODIN_HTTP_JWKS_INLINE", json.dumps(jwks))

    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    hdr = sign_v1(method="POST", path="/task", body=body, kid="k1", priv=priv)

    r2 = client.post(
        "/task",
        content=body,
        headers={"content-type": "application/json", "X-ODIN-HTTP-Signature": hdr},
    )
    assert r2.status_code == 200, r2.text
