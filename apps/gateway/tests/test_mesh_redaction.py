import os
from fastapi.testclient import TestClient


def test_mesh_receipt_redaction(monkeypatch):
    # Activate in-memory storage and router id
    monkeypatch.setenv("ODIN_STORAGE_BACKEND", "inmem")
    monkeypatch.setenv("ODIN_ROUTER_ID", "routerA")
    # Redact nested fields and wildcard list secrets
    monkeypatch.setenv("ODIN_REDACT_FIELDS", "payload.secret,user.password,items.*.token")

    from apps.gateway import api as gateway_api
    c = TestClient(gateway_api.app)

    body = {
        "payload": {
            "secret": "hide-me",
            "user": {"password": "p@ss", "name": "ok"},
            "items": [{"token": "t1"}, {"token": "t2"}, {"note": "n"}],
        }
    }
    r = c.post("/v1/mesh/forward", json=body)
    assert r.status_code == 200

    # Fetch the hop receipt document and assert fields redacted
    href = r.headers.get("X-ODIN-Hop-Receipt-URL")
    assert href and href.startswith("/v1/receipts/hops/")
    rec = c.get(href)
    assert rec.status_code == 200
    j = rec.json()

    # Confirm redactions occurred only in stored receipt
    assert j["in"]["secret"] == "***"
    assert j["in"]["user"]["password"] == "***"
    assert [x.get("token") for x in j["in"]["items"][:2]] == ["***", "***"]
    # Unmatched fields preserved
    assert j["in"]["user"]["name"] == "ok"
    assert j["in"]["items"][2]["note"] == "n"

    # The HTTP response body should not be redacted (we don't modify outbound body)
    out = r.json()
    assert out.get("payload") is None  # our forwarder returns minimal body by default
