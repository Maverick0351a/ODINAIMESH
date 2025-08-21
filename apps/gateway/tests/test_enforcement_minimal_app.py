from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.gateway.middleware.proof_enforcement import (
    ProofEnforcementMiddleware,
    ENV_ENFORCE_ROUTES,
    ENV_POLICY_PATH,
)
from libs.odin_core.odin.ope import OpeKeypair, sign_over_content
from libs.odin_core.odin.cid import compute_cid
from libs.odin_core.odin.envelope import ProofEnvelope


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_app(policy_path: str | None = None):
    app = FastAPI()
    os.environ[ENV_ENFORCE_ROUTES] = "/v1/secured"
    if policy_path:
        os.environ[ENV_POLICY_PATH] = policy_path
    app.add_middleware(ProofEnforcementMiddleware)

    @app.post("/v1/secured/echo")
    async def secured_echo(body: dict):
        # Middleware verified and may unwrap the payload
        return JSONResponse({"ok": True, "payload": body.get("payload", body)})

    @app.post("/open/echo")
    async def open_echo(body: dict):
        return {"ok": True, "payload": body}

    return app


def build_envelope(payload: dict, kid_override: str | None = None, jwks_inline: bool = True):
    # For this minimal test, canonical bytes = compact JSON bytes
    oml_c_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    cid = compute_cid(oml_c_bytes)

    kp = OpeKeypair.generate(kid_override or "k1")
    ope = sign_over_content(kp, oml_c_bytes, oml_cid=cid)

    jwks = (
        {
            "keys": [
                {
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": kp.pub_b64u(),
                    "kid": kp.kid,
                    "alg": "EdDSA",
                    "use": "sig",
                }
            ]
        }
        if jwks_inline
        else None
    )

    env = ProofEnvelope.from_ope(
        oml_c_bytes=oml_c_bytes,
        ope=ope,
        jwks_url=None if jwks_inline else "http://test/jwks",
        jwks_inline=jwks,
        include_oml_c_b64=True,
    )
    return json.loads(env.to_json())


def test_enforcement_happy_path_inline_jwks():
    app = make_app()
    client = TestClient(app)
    payload = {"x": 1}
    proof = build_envelope(payload, jwks_inline=True)

    r = client.post("/v1/secured/echo", json={"payload": payload, "proof": proof})
    assert r.status_code == 200, r.text
    assert r.json()["payload"] == payload


def test_enforcement_missing_proof_401():
    app = make_app()
    client = TestClient(app)
    payload = {"x": 2}

    r = client.post("/v1/secured/echo", json={"payload": payload})
    assert r.status_code == 401
    assert r.json()["error"] == "odin.proof.missing"


def test_policy_blocked_kid_403(tmp_path: Path):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps({"allow_kids": ["*"], "deny_kids": ["*"], "allowed_jwks_hosts": ["*"]}), encoding="utf-8")

    app = make_app(policy_path=str(p))
    client = TestClient(app)
    payload = {"y": 3}
    proof = build_envelope(payload, jwks_inline=True)

    r = client.post("/v1/secured/echo", json={"payload": payload, "proof": proof})
    assert r.status_code == 403
    assert r.json()["error"] == "odin.policy.blocked"


def test_unenforced_route_passes_without_proof():
    app = make_app()
    client = TestClient(app)
    payload = {"z": 9}
    r = client.post("/open/echo", json=payload)
    assert r.status_code == 200
    assert r.json()["payload"] == payload
