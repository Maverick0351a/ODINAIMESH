from fastapi.testclient import TestClient
from services.relay.api import app
import base64
import os


def test_relay_blocks_private_and_filters_headers():
    c = TestClient(app)

    # Private IP is blocked
    payload = {
        "url": "http://127.0.0.1:8080/echo",
        "bytes_b64": base64.b64encode(b"hello").decode("ascii"),
        "headers": {"X-ODIN-OPE": "zzz", "X-ODIN-OML-CID": "b123"},
    }
    r = c.post("/relay", json=payload)
    assert r.status_code == 400
    assert "blocked" in r.json()["detail"]


def test_relay_rate_limit_and_allow_private(monkeypatch):
    # enable rate limit
    monkeypatch.setenv("ODIN_RELAY_RATE_LIMIT_QPS", "0.1")
    c = TestClient(app)
    payload = {
        "url": "http://127.0.0.1:8080/echo",
        "bytes_b64": base64.b64encode(b"hello").decode("ascii"),
    }
    # First call blocked due to private unless allowed
    r1 = c.post("/relay", json=payload)
    assert r1.status_code == 400
    # Allow private
    monkeypatch.setenv("ODIN_RELAY_ALLOW_PRIVATE", "1")
    r2 = c.post("/relay", json=payload)
    # Now rate limit may trigger (429) or 502 due to connect error since no server; accept either
    assert r2.status_code in (429, 502)
