import json
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from libs.odin_core.odin.http_sig import sign_v1, _b64u_nopad  # uses http_sig helpers


def test_agent_beta_signature_metrics(monkeypatch):
    from apps.agent_beta import api as beta_api

    # Ensure a fresh app client per test
    client = TestClient(beta_api.app)

    # Enforce signatures
    monkeypatch.setenv("ODIN_HTTP_SIGN_REQUIRE", "1")

    payload = {
        "intent": "beta.request",
        "prompt": "p",
        "why": "w",
        "arguments": {"a": 2, "b": 2},
    }

    # 1) Missing signature -> 401 and metrics 'missing' or 'fail'
    r = client.post("/task", json=payload)
    assert r.status_code == 401

    # 2) Signed path -> 200
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    jwks = {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": "k1", "x": _b64u_nopad(pub)}]}
    monkeypatch.setenv("ODIN_HTTP_JWKS_INLINE", json.dumps(jwks))

    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    hdr = sign_v1(method="POST", path="/task", body=body, kid="k1", priv=priv)

    r2 = client.post(
        "/task",
        content=body,
        headers={"content-type": "application/json", "X-ODIN-HTTP-Signature": hdr},
    )
    assert r2.status_code == 200

    # 3) Metrics should reflect outcomes for agent_beta
    m = client.get("/metrics").text
    # Don't rely on label order; ensure family and labels are present
    assert "odin_httpsig_verifications_total" in m
    assert 'service="agent_beta"' in m
    assert 'outcome="pass"' in m
    assert ('outcome="missing"' in m) or ('outcome="fail"' in m)
