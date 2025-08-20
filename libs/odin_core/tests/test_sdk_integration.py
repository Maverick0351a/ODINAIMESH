from __future__ import annotations

import base64
import json
from typing import Dict, Any

import httpx
import pytest

from odin_core.odin.sdk import OdinHttpClient
from odin_core.odin.ope import OpeKeypair, sign_over_content
from odin_core.odin.oml import to_oml_c
from odin_core.odin.envelope import ProofEnvelope


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_transport() -> httpx.MockTransport:
    last_jwks: Dict[str, Dict[str, Any]] = {"value": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/.well-known/odin/jwks.json":
            return httpx.Response(200, json=last_jwks["value"] or {"keys": []})

        if request.method == "POST" and request.url.path == "/v1/envelope":
            payload = json.loads(request.content.decode("utf-8"))
            # Canonicalize to OML-C using real encoder
            oml_c = to_oml_c(payload)

            # Sign using OPE
            kp = OpeKeypair.generate("k1")
            env_ope = sign_over_content(kp, oml_c, None)

            # Publish JWKS for this request
            last_jwks["value"] = {
                "keys": [
                    {
                        "kty": "OKP",
                        "crv": "Ed25519",
                        "x": env_ope["pub_b64u"],
                        "kid": env_ope["kid"],
                        "alg": "EdDSA",
                        "use": "sig",
                    }
                ]
            }

            env = ProofEnvelope.from_ope(
                oml_c_bytes=oml_c,
                ope=env_ope,
                jwks_url="/.well-known/odin/jwks.json",
                include_oml_c_b64=True,
            )
            body = {"payload": payload, "proof": json.loads(env.to_json())}
            return httpx.Response(200, json=body)

        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_sdk_post_envelope_verifies_via_jwks_header():
    transport = make_transport()
    client = httpx.Client(transport=transport, base_url="http://testserver")
    sdk = OdinHttpClient(base_url="http://testserver", client=client, require_proof=True)
    try:
        payload = {"x": 1, "y": 2}
        body, ver = sdk.post_envelope("/v1/envelope", payload)
        assert body == payload
        assert ver.ok is True
        assert ver.cid and ver.kid
    finally:
        sdk.close()
