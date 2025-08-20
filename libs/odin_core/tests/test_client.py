from __future__ import annotations

import json
from typing import Any, Dict

import httpx
import pytest

from odin.client import OdinHttpClient
from odin.constants import ACCEPT_PROOF_HEADER, DEFAULT_ACCEPT_PROOF


@pytest.fixture
def mock_server_response() -> Dict[str, Any]:
    # Minimal plausible envelope for tests; verifier will treat JWKS as optional.
    return {
        "payload": {"ok": True},
        "proof": {
            "oml_cid": "bd4qexamplecid",
            "kid": "k1",
            "ope": "e30",  # base64url of '{}' -> '{}', but will fail verification; client should surface failure
            "oml_c_b64": "AA",  # base64url of minimal bytes; not valid CBOR but not decoded here
        },
    }


def test_client_requires_proof_and_surfaces_failure(mock_server_response):
    # Setup MockTransport
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/v1/envelope"):
            return httpx.Response(200, json=mock_server_response)
        if request.method == "GET" and request.url.path.endswith("/.well-known/odin/jwks.json"):
            return httpx.Response(200, json={"keys": []})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://example.com")

    sdk = OdinHttpClient(base_url="http://example.com", client=client, require_proof=False)
    payload, ver = sdk.post_envelope("/v1/envelope", {"x": 1})
    assert payload == {"ok": True}
    assert ver.ok is False
    assert ver.reason

    # When require_proof=True and proof verification fails, it should raise
    sdk2 = OdinHttpClient(base_url="http://example.com", client=client, require_proof=True)
    with pytest.raises(ValueError):
        sdk2.post_envelope("/v1/envelope", {"x": 1})


def test_client_sends_accept_proof_header_by_default(mock_server_response):
    seen = {"header": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/v1/envelope"):
            seen["header"] = request.headers.get(ACCEPT_PROOF_HEADER)
            return httpx.Response(200, json=mock_server_response)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://example.com")
    sdk = OdinHttpClient(base_url="http://example.com", client=client, require_proof=False)
    payload, ver = sdk.post_envelope("/v1/envelope", {"x": 1})
    assert payload == {"ok": True}
    assert seen["header"] == DEFAULT_ACCEPT_PROOF


def test_client_does_not_override_caller_accept_proof_header(mock_server_response):
    seen = {"header": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/v1/envelope"):
            seen["header"] = request.headers.get(ACCEPT_PROOF_HEADER)
            return httpx.Response(200, json=mock_server_response)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://example.com")
    sdk = OdinHttpClient(base_url="http://example.com", client=client, require_proof=False)
    # Caller provides a specific negotiation choice; SDK should not override it
    headers = {ACCEPT_PROOF_HEADER: "headers"}
    payload, ver = sdk.post_envelope("/v1/envelope", {"x": 1}, headers=headers)
    assert payload == {"ok": True}
    assert seen["header"] == "headers"
