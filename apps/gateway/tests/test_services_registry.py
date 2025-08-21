from fastapi.testclient import TestClient
import time
import json

def _advert(id="beta", ttl=5):
    return {
        "intent": "service.advertise",
        "id": id,
        "name": "Agent Beta",
        "jwks_url": "/.well-known/odin/jwks.json",
        "endpoints": {"task": "/task"},
        "intents": ["beta.request", "beta.reply"],
        "tags": ["agent", "math"],
        "ttl_s": ttl,
        "metadata": {"version": "1.0.0"},
    }

def test_register_and_list(monkeypatch):
    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    body = _advert(id="beta1", ttl=30)
    r = client.post("/v1/services/register", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["id"] == "beta1"
    assert j["ttl_s"] <= 30

    # list all
    r2 = client.get("/v1/services")
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["count"] >= 1
    assert any(s["id"] == "beta1" for s in j2["services"])

    # filter by intent
    r3 = client.get("/v1/services", params={"intent": "beta.request"})
    assert r3.status_code == 200
    j3 = r3.json()
    assert any(s["id"] == "beta1" for s in j3["services"])

    # filter by tag
    r4 = client.get("/v1/services", params={"tag": "math"})
    assert r4.status_code == 200
    j4 = r4.json()
    assert any(s["id"] == "beta1" for s in j4["services"])

    # fetch one
    r5 = client.get("/v1/services/beta1")
    assert r5.status_code == 200
    j5 = r5.json()
    assert j5["name"] == "Agent Beta"
    assert j5["endpoints"]["task"] == "/task"

def test_ttl_expiry(monkeypatch):
    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    # tiny TTL; then simulate time passing by monkeypatching time.time
    body = _advert(id="beta2", ttl=1)
    r = client.post("/v1/services/register", json=body)
    assert r.status_code == 200

    # Move time forward by 2 seconds
    import apps.gateway.services as svc
    real_time = svc.time
    class _FakeTime:
        @staticmethod
        def time():
            return real_time.time() + 2.0
    monkeypatch.setattr(svc, "time", _FakeTime)

    # Listing should GC the expired service
    r2 = client.get("/v1/services")
    j2 = r2.json()
    assert all(s["id"] != "beta2" for s in j2["services"])

    r3 = client.get("/v1/services/beta2")
    assert r3.status_code == 404
