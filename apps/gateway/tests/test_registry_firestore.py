import os
import pytest
from fastapi.testclient import TestClient

skip = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator not running",
)

@skip
def test_registry_firestore_roundtrip(monkeypatch):
    monkeypatch.setenv("ODIN_REGISTRY_BACKEND", "firestore")
    monkeypatch.setenv("ODIN_FIRESTORE_COLLECTION", "odin_registry_test")

    from apps.gateway import api as gateway_api
    c = TestClient(gateway_api.app)

    ad = {
        "intent": "odin.service.advertise",
        "service": "agent_beta",
        "version": "v1",
        "base_url": "http://127.0.0.1:9090",
        "sft": ["beta@v1"],
        "ttl_s": 60,
    }
    env_resp = c.post("/v1/envelope", json=ad)
    assert env_resp.status_code == 200
    env = env_resp.json()["proof"]

    r = c.post("/v1/registry/register", json={"payload": ad, "proof": env})
    assert r.status_code == 200
    rid = r.json()["id"]

    g = c.get(f"/v1/registry/services/{rid}")
    assert g.status_code == 200
    assert g.json()["payload"]["service"] == "agent_beta"
