import os
import pytest
import httpx


RELAY_URL = os.environ.get("RELAY_URL", "").rstrip("/")


pytestmark = pytest.mark.skipif(not RELAY_URL, reason="RELAY_URL not set")


def _url(path: str) -> str:
    return f"{RELAY_URL}{path}"


def test_metrics():
    r = httpx.get(_url("/metrics"), timeout=20.0)
    # Auth-required deployments may return 401/403; make this a soft check
    if r.status_code in (401, 403):
        pytest.skip("metrics requires auth")
    assert r.status_code == 200


def test_relay_httpbin():
    body = {"method": "GET", "url": "https://httpbin.org/json"}
    r = httpx.post(_url("/relay"), json=body, timeout=30.0)
    assert 200 <= r.status_code < 300


def test_relay_ssrf_block():
    body = {"method": "GET", "url": "http://169.254.169.254/latest/meta-data/"}
    r = httpx.post(_url("/relay"), json=body, timeout=20.0)
    assert not (200 <= r.status_code < 300)
