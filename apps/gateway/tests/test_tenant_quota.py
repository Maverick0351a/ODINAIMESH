from __future__ import annotations

import os
from fastapi.testclient import TestClient
from apps.gateway import api as gateway_api


def test_tenant_quota_enforced(monkeypatch):
    # Use a low quota and per-tenant override to ensure determinism
    monkeypatch.setenv("ODIN_TENANT_QUOTA_MONTHLY_REQUESTS", "0")  # default disabled
    monkeypatch.setenv("ODIN_TENANT_QUOTA_OVERRIDES", "acme=2")

    c = TestClient(gateway_api.app)
    h = {os.getenv("ODIN_TENANT_HEADER", "X-ODIN-Tenant"): "acme"}

    # Two requests pass
    r1 = c.get("/health", headers=h)
    assert r1.status_code == 200  # exempt path should not count or block
    r2 = c.get("/whoami", headers=h)
    assert r2.status_code == 200
    r3 = c.get("/whoami", headers=h)
    # With quota=2, by the third/fourth call we must see a 429, and never exceed 2 successes.
    codes = [r2.status_code, r3.status_code]
    if r3.status_code != 429:
        r4 = c.get("/whoami", headers=h)
        codes.append(r4.status_code)
    # No more than two 200s should be observed
    assert sum(1 for c0 in codes if c0 == 200) <= 2
    # And at least one 429 must appear
    assert any(c0 == 429 for c0 in codes)


def test_quota_not_enforced_without_env(monkeypatch):
    monkeypatch.delenv("ODIN_TENANT_QUOTA_MONTHLY_REQUESTS", raising=False)
    monkeypatch.delenv("ODIN_TENANT_QUOTA_OVERRIDES", raising=False)
    c = TestClient(gateway_api.app)
    r = c.get("/whoami", headers={"X-ODIN-Tenant": "acme"})
    assert r.status_code == 200
