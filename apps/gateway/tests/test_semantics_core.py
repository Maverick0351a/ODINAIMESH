from fastapi.testclient import TestClient
from apps.gateway.api import app


def test_core_semantics_well_known():
    c = TestClient(app)
    r = c.get("/.well-known/odin/semantics/core@v0.1.json")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("id") == "core@v0.1"
    assert "fields" in body and isinstance(body["fields"], dict)
    assert "intents" in body and isinstance(body["intents"], dict)
    # sanity: required field present
    assert body["fields"]["intent"]["required"] is True
