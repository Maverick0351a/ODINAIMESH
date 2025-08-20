from fastapi.testclient import TestClient
from apps.gateway.api import app


def test_core_sft_endpoint():
    c = TestClient(app)
    r = c.get("/v1/sft/core")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "core@v0.1"
    assert isinstance(body.get("cid"), str)
    assert isinstance(body.get("json_sha256"), str)
    assert isinstance(body.get("sft"), dict)
