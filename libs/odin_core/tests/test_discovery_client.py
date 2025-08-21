from __future__ import annotations

import json

import httpx

from odin.discovery import discovery_url, fetch_discovery, Discovery


def test_discovery_url_builder():
    assert discovery_url("http://x") == "http://x/.well-known/odin/discovery.json"
    assert discovery_url("http://x/") == "http://x/.well-known/odin/discovery.json"


def test_fetch_discovery_and_parse():
    # Minimal discovery doc
    doc = {
        "jwks_url": "http://example.com/.well-known/odin/jwks.json",
        "endpoints": {"jwks": "/.well-known/odin/jwks.json", "health": "/health"},
        "policy": {"sign_routes": [], "enforce_routes": [], "sign_embed": False},
        "protocol": {"odin": "0.1", "proof_version": "1"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/.well-known/odin/discovery.json"):
            return httpx.Response(200, json=doc)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    d = fetch_discovery("http://example.com", transport=transport)
    assert isinstance(d, Discovery)
    assert d.jwks_url == doc["jwks_url"]
    assert d.endpoints.get("jwks") == "/.well-known/odin/jwks.json"
    assert d.protocol.get("odin") == "0.1"


def test_from_dict_requires_jwks_url():
    # Missing jwks entirely -> ValueError
    try:
        Discovery.from_dict({"endpoints": {}})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "jwks_url" in str(e)


def test_fetch_discovery_parses_core_fields():
    """Ensure additional core fields are preserved in the parsed Discovery object."""
    body = {
        "jwks_url": "http://gw.test/.well-known/odin/jwks.json",
        "endpoints": {"jwks": "/.well-known/odin/jwks.json", "verify": "/v1/verify"},
        "policy": {"enforce_routes": [], "sign_routes": [], "sign_embed": False},
        "protocol": {"odin": "0.1", "proof_version": "1"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/odin/discovery.json"):
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    d = fetch_discovery("http://gw.test", transport=transport)
    assert d.jwks_url.endswith("/.well-known/odin/jwks.json")
    assert "verify" in d.endpoints
    assert d.policy.get("sign_embed") is False
    assert d.protocol.get("proof_version") == "1"
