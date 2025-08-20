from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gateway.sft import router as sft_router
from apps.gateway.middleware.response_signing import ResponseSigningMiddleware, ENV_SIGN_ROUTES, ENV_SIGN_REQUIRE, ENV_SIGN_EMBED
from odin_core.odin.sft import CORE_ID, sft_info

def make_app():
    os.environ[ENV_SIGN_ROUTES] = "/v1"
    os.environ[ENV_SIGN_REQUIRE] = "1"
    os.environ[ENV_SIGN_EMBED] = "1"

    app = FastAPI()
    app.include_router(sft_router)

    @app.post("/v1/translate")
    def translate_echo(payload: dict):
        # mimic a translator that returns transformed payload (here, echo)
        return payload

    app.add_middleware(ResponseSigningMiddleware)
    return app

def test_sft_core_endpoint():
    app = make_app()
    c = TestClient(app)

    r = c.get("/v1/sft/core")
    assert r.status_code == 200
    body = r.json()
    # If response signing embedded the payload, unwrap it
    payload = body.get("payload") if isinstance(body, dict) and "payload" in body else body
    assert payload["id"] == CORE_ID
    assert "cid" in payload and "json_sha256" in payload and "sft" in payload

def test_translate_valid_gets_signed_with_sft():
    app = make_app()
    c = TestClient(app)

    payload = {"intent": "echo", "amount": 7}
    r = c.post("/v1/translate", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "proof" in data and "payload" in data
    assert data["proof"].get("sft_id") == CORE_ID

def test_translate_invalid_amount_rejected_422(monkeypatch):
    # Enable pre-sign SFT validation for /v1/translate
    monkeypatch.setenv("ODIN_SFT_VALIDATE_ROUTES", "/v1/translate")

    app = make_app()
    c = TestClient(app)

    bad = {"intent": "transfer", "amount": "10"}
    r = c.post("/v1/translate", json=bad)
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "odin.sft.invalid"
    paths = [d["path"] for d in body["details"]]
    assert "/amount" in paths
