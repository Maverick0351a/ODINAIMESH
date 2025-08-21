from __future__ import annotations

import os

from fastapi.testclient import TestClient

from apps.gateway.api import app


def test_discovery_basic(monkeypatch):
    # Configure env so the document reflects enforcement/signing at request time
    monkeypatch.setenv("ODIN_ENFORCE_ROUTES", "/v1/envelope,/v1/secured")
    monkeypatch.setenv("ODIN_SIGN_ROUTES", "/v1/echo")
    monkeypatch.setenv("ODIN_SIGN_EMBED", "1")

    c = TestClient(app)
    r = c.get("/.well-known/odin/discovery.json")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control", "").startswith("public")

    body = r.json()
    assert body["service"] == "gateway"
    assert body["protocol"]["odin"].startswith("0.")
    assert body["jwks_url"].endswith("/.well-known/odin/jwks.json")

    # Endpoints advertised
    eps = body["endpoints"]
    for key in ("echo", "translate", "envelope", "verify", "receipts", "jwks", "discovery"):
        assert key in eps and isinstance(eps[key], str)

    # Policy echo
    pol = body["policy"]
    assert "/v1/envelope" in pol["enforce_routes"]
    assert "/v1/echo" in pol["sign_routes"]
    assert pol["sign_embed"] is True

    # Capabilities should at least contain envelope & verify
    caps = body["capabilities"]
    assert "envelope" in caps and "verify" in caps


def test_discovery_reflects_routes_presence():
    c = TestClient(app)
    r = c.get("/.well-known/odin/discovery.json")
    body = r.json()
    # We know /health exists; discovery should always be reachable too
    assert body["endpoints"]["health"] == "/health"
    assert body["endpoints"]["discovery"] == "/.well-known/odin/discovery.json"


def test_discovery_has_transform_index():
    c = TestClient(app)
    r = c.get("/.well-known/odin/discovery.json")
    assert r.status_code == 200
    doc = r.json()
    assert doc["capabilities"].get("transform_index") is True
    assert "/v1/receipts/transform" in doc["endpoints"].get("receipts_transform_list", "")
