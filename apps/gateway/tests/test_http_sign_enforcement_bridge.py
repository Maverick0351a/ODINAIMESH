import os, json, base64, importlib
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from libs.odin_core.odin.http_sig import sign_v1


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _make_jwks(pub: bytes) -> dict:
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": "k1", "x": _b64u(pub)}]}


def _prep_env_for_bridge_enforcement():
    os.environ["ODIN_HTTP_SIGN_ENFORCE_ROUTES"] = "/v1/bridge"
    os.environ["ODIN_HTTP_SIGN_REQUIRE"] = "1"
    os.environ["ODIN_HTTP_SIGN_SKEW_SEC"] = "300"


def _reload_gateway():
    import apps.gateway.api as gateway_api
    importlib.reload(gateway_api)
    return gateway_api.app


def test_bridge_requires_httpsig_and_accepts_valid():
    _prep_env_for_bridge_enforcement()
    
    # Set up a test realm pack with permissive egress allowlist
    os.environ["ODIN_REALM_PACK_URI"] = "packs/realms/business-1.0.0/"
    
    # generate keypair and publish JWKS inline
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    os.environ["ODIN_HTTP_JWKS_INLINE"] = json.dumps(_make_jwks(pub))

    app = _reload_gateway()
    client = TestClient(app)

    # Minimal valid body for /v1/bridge (identity translation) — alpha@v1 requires specific intents
    # Use alpha.result which requires fields: answer (str) and ok (bool)
    body_obj = {
        "payload": {"intent": "alpha.result", "answer": "ok", "ok": True},
        "from_sft": "alpha@v1",
        "to_sft": "alpha@v1",
    }
    body = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    # 1) Missing signature -> 401
    r1 = client.post("/v1/bridge", content=body, headers={"content-type": "application/json"})
    assert r1.status_code == 401
    assert "odin.http_sig.missing" in r1.text

    # 2) Valid signature -> 200
    hdr = sign_v1(method="POST", path="/v1/bridge", body=body, kid="k1", priv=priv)
    r2 = client.post(
        "/v1/bridge",
        content=body,
        headers={"content-type": "application/json", "X-ODIN-HTTP-Signature": hdr},
    )
    assert r2.status_code == 200, r2.text

    # Cleanup: clear env and reload gateway to remove enforcement for other tests
    for k in [
        "ODIN_HTTP_SIGN_ENFORCE_ROUTES",
        "ODIN_HTTP_SIGN_REQUIRE",
        "ODIN_HTTP_JWKS_INLINE",
        "ODIN_HTTP_SIGN_SKEW_SEC",
    ]:
        os.environ.pop(k, None)
    import apps.gateway.api as gateway_api
    importlib.reload(gateway_api)
