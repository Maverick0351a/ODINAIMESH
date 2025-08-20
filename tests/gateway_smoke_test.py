import os
import pytest
import httpx


GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")


pytestmark = pytest.mark.skipif(not GATEWAY_URL, reason="GATEWAY_URL not set")


def _url(path: str) -> str:
    return f"{GATEWAY_URL}{path}"


def test_metrics():
    r = httpx.get(_url("/metrics"), timeout=20.0)
    assert r.status_code == 200
    assert "# HELP" in r.text or "odin_" in r.text


def test_envelope_basic():
    payload = {"payload": {"hello": "world"}}
    r = httpx.post(_url("/v1/envelope"), json=payload, timeout=30.0)
    # Some builds may not expose /v1/envelope; accept 404 as soft-fail
    if r.status_code == 404:
        pytest.skip("/v1/envelope not available on this deployment")
    assert 200 <= r.status_code < 300
