import os, json, base64, importlib
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from libs.odin_core.odin.http_sig import sign_v1


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _make_jwks(pub: bytes) -> dict:
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": "k1", "x": _b64u(pub)}]}


def _prep_env_for_echo_enforcement():
    os.environ["ODIN_HTTP_SIGN_ENFORCE_ROUTES"] = "/v1/echo"
    os.environ["ODIN_HTTP_SIGN_REQUIRE"] = "1"
    # JWKS will be set per-test after we generate a key
    os.environ["ODIN_HTTP_SIGN_SKEW_SEC"] = "300"


def _reload_gateway():
    import apps.gateway.api as gateway_api
    importlib.reload(gateway_api)
    return gateway_api.app


def test_http_sign_required_and_valid():
    _prep_env_for_echo_enforcement()
    # generate keypair and publish JWKS inline
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    os.environ["ODIN_HTTP_JWKS_INLINE"] = json.dumps(_make_jwks(pub))

    app = _reload_gateway()
    client = TestClient(app)

    body_obj = {"hello": "world"}
    body = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    # 1) Missing signature -> 401
    r1 = client.post("/v1/echo", content=body, headers={"content-type": "application/json"})
    assert r1.status_code == 401
    assert "odin.http_sig.missing" in r1.text

    # 2) Valid signature -> 200
    hdr = sign_v1(method="POST", path="/v1/echo", body=body, kid="k1", priv=priv)
    r2 = client.post(
        "/v1/echo",
        content=body,
        headers={"content-type": "application/json", "X-ODIN-HTTP-Signature": hdr},
    )
    assert r2.status_code == 200, r2.text

    try:
        # 3) Tamper body -> 401
        bad_body = json.dumps({"hello": "mars"}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        r3 = client.post(
            "/v1/echo",
            content=bad_body,
            headers={"content-type": "application/json", "X-ODIN-HTTP-Signature": hdr},  # stale header
        )
        assert r3.status_code == 401
        assert "odin.http_sig.invalid" in r3.text
    finally:
        # Cleanup: clear env and reload gateway to remove enforcement for other tests
        for k in [
            "ODIN_HTTP_SIGN_ENFORCE_ROUTES",
            "ODIN_HTTP_SIGN_REQUIRE",
            "ODIN_HTTP_JWKS_INLINE",
            "ODIN_HTTP_SIGN_SKEW_SEC",
        ]:
            os.environ.pop(k, None)
        # reload gateway module to rebuild app without enforcement
        import apps.gateway.api as gateway_api
        importlib.reload(gateway_api)
