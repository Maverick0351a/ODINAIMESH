from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from apps.gateway.middleware.response_signing import (
    ResponseSigningMiddleware,
    ENV_SIGN_ROUTES,
    ENV_SIGN_REQUIRE,
    ENV_SIGN_EMBED,
    HDR_ACCEPT_PROOF,
    HDR_PROOF_STATUS,
)


def make_app() -> FastAPI:
    os.environ[ENV_SIGN_ROUTES] = "/v1/enforced"
    os.environ[ENV_SIGN_REQUIRE] = "1"
    os.environ[ENV_SIGN_EMBED] = "1"
    app = FastAPI()
    app.add_middleware(ResponseSigningMiddleware)

    @app.get("/v1/enforced/json")
    def enforced_json():
        return {"ok": True}

    @app.get("/v1/enforced/text")
    def enforced_text():
        return PlainTextResponse("raw", media_type="text/plain")

    @app.get("/open/json")
    def open_json():
        return {"ok": True}

    @app.get("/open/text")
    def open_text():
        return PlainTextResponse("raw", media_type="text/plain")

    return app


class TestProofNegotiation:
    def test_required_on_open_json_triggers_signing(self):
        app = make_app()
        c = TestClient(app)
        r = c.get("/open/json", headers={HDR_ACCEPT_PROOF: "required"})
        assert r.status_code == 200
        assert r.headers.get("X-ODIN-OPE"), "must be signed"
        assert r.headers.get(HDR_PROOF_STATUS) == "signed"
        body = r.json()
        assert "proof" in body and "payload" in body

    def test_required_on_open_text_returns_406(self):
        app = make_app()
        c = TestClient(app)
        r = c.get("/open/text", headers={HDR_ACCEPT_PROOF: "required"})
        assert r.status_code == 406
        assert r.json()["error"] == "odin.proof.required"
        assert r.headers.get(HDR_PROOF_STATUS) == "absent"

    def test_none_on_enforced_is_ignored_but_signed(self):
        app = make_app()
        c = TestClient(app)
        r = c.get("/v1/enforced/json", headers={HDR_ACCEPT_PROOF: "none"})
        assert r.status_code == 200
        assert r.headers.get("X-ODIN-OPE")
        assert r.headers.get(HDR_PROOF_STATUS) in ("ignored", "signed")
        body = r.json()
        assert "proof" in body

    def test_if_available_on_open_text_passes_without_proof(self):
        app = make_app()
        c = TestClient(app)
        r = c.get("/open/text", headers={HDR_ACCEPT_PROOF: "if-available"})
        assert r.status_code == 200
        assert "X-ODIN-OPE" not in r.headers
        assert r.headers.get(HDR_PROOF_STATUS) == "absent"
