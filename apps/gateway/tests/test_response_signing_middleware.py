from __future__ import annotations

import importlib
import os
import json
from fastapi.testclient import TestClient


def _reload_app_with_env(env: dict[str, str]):
    # Clear module to force re-import with new env
    import apps.gateway.api as api
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    import sys
    if "apps.gateway.api" in sys.modules:
        del sys.modules["apps.gateway.api"]
    import apps.gateway.api as api
    importlib.reload(api)
    return api.app


def test_signs_json_response_adds_headers(tmp_path):
    # Configure signing for /v1/echo only
    app = _reload_app_with_env({
        "ODIN_SIGN_ROUTES": "/v1/echo",
        "ODIN_SIGN_REQUIRE": "1",
        "ODIN_SIGN_EMBED": "0",
        "ODIN_DATA_DIR": str(tmp_path / "data"),
        "ODIN_TMP_DIR": str(tmp_path / "tmp"),
    })
    client = TestClient(app)

    r = client.post("/v1/echo", json={"message": "hi"})
    assert r.status_code == 200
    # Should include signing headers
    assert r.headers.get("X-ODIN-OML-CID")
    assert r.headers.get("X-ODIN-OPE")
    assert r.headers.get("X-ODIN-OPE-KID")
    # Discovery middleware should add JWKS path
    assert r.headers.get("X-ODIN-JWKS") == "/.well-known/odin/jwks.json"

    # Body remains original when not embedding
    body = r.json()
    assert body == {"echo": "hi"}


def test_embed_envelope_when_enabled(tmp_path):
    app = _reload_app_with_env({
        "ODIN_SIGN_ROUTES": "/v1/echo",
        "ODIN_SIGN_REQUIRE": "1",
        "ODIN_SIGN_EMBED": "1",
        "ODIN_DATA_DIR": str(tmp_path / "data"),
        "ODIN_TMP_DIR": str(tmp_path / "tmp"),
    })
    client = TestClient(app)

    r = client.post("/v1/echo", json={"message": "hello"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "payload" in body and "proof" in body
    assert body["payload"] == {"echo": "hello"}


def test_non_json_response_left_unsigned(tmp_path):
    # For /metrics which is not JSON (text/plain), no signing headers expected even if prefix matches
    app = _reload_app_with_env({
        "ODIN_SIGN_ROUTES": "/metrics",
        "ODIN_SIGN_REQUIRE": "1",
        "ODIN_SIGN_EMBED": "0",
        "ODIN_DATA_DIR": str(tmp_path / "data"),
        "ODIN_TMP_DIR": str(tmp_path / "tmp"),
    })
    client = TestClient(app)

    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers.get("X-ODIN-OPE") is None
