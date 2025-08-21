from __future__ import annotations

import base64
import json
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gateway.middleware.response_signing import (
    ResponseSigningMiddleware,
    ENV_SIGN_ROUTES, ENV_SIGN_REQUIRE, ENV_SIGN_EMBED,
    X_OML_CID, X_OML_C_PATH, X_OPE, X_OPE_KID, X_JWKS, HDR_PROOF_STATUS,
    WELL_KNOWN_JWKS,
)
from odin_core.odin.ope import sign_ope
from odin_core.odin.proof import ProofEnvelope


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_app():
    os.environ[ENV_SIGN_ROUTES] = "/duel"
    os.environ[ENV_SIGN_REQUIRE] = "1"
    os.environ[ENV_SIGN_EMBED] = "1"
    app = FastAPI()
    app.add_middleware(ResponseSigningMiddleware)

    @app.get("/duel/body")
    def duel_body():
        payload = {"ok": True, "n": 1}
        oml_c_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig_b, kid, pub_b = sign_ope(oml_c_bytes)
        env = ProofEnvelope.from_parts(
            oml_c_bytes=oml_c_bytes,
            kid=kid,
            sig_b=sig_b,
            jwks_url=WELL_KNOWN_JWKS,
            jwks_inline={"keys": [{"kty": "OKP", "crv": "Ed25519", "x": b64url(pub_b), "kid": kid, "alg": "EdDSA", "use": "sig"}]},
            include_oml_c_b64=True,
        )
        return {"payload": payload, "proof": json.loads(env.to_json())}

    return app


def test_dual_channel_headers_from_envelope(tmp_path, monkeypatch):
    # Ensure data dir is under tmp to avoid polluting repo
    monkeypatch.setenv("ODIN_DATA_DIR", str(tmp_path))

    app = make_app()
    c = TestClient(app)

    r = c.get("/duel/body")
    assert r.status_code == 200, r.text
    body = r.json()
    proof = body["proof"]

    # Dual channel: headers mirror envelope
    assert r.headers.get(X_OML_CID) == proof["oml_cid"]
    assert r.headers.get(X_OPE) == proof["ope"]
    assert r.headers.get(X_OPE_KID) == proof["kid"]
    assert r.headers.get(X_JWKS)  # jwks url present (envelope or well-known)
    assert r.headers.get(HDR_PROOF_STATUS) == "signed"

    # When oml_c_b64 was present, we should also persist and expose path
    oml_path = r.headers.get(X_OML_C_PATH)
    assert oml_path and os.path.isfile(oml_path)

    # Body remains the same envelope (no double-wrapping)
    assert "payload" in body and "proof" in body
