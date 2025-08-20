import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routers.receipts import router as receipts_router
from gateway.constants import ENV_DATA_DIR


def test_get_receipt_happy_path(tmp_path, monkeypatch):
    data_dir = tmp_path / "odin"
    receipts_dir = data_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    cid = "bafkqaaa-example"
    payload = {"oml_cid": cid, "ope": "sig", "kid": "kid1"}
    path = receipts_dir / f"{cid}.ope.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv(ENV_DATA_DIR, str(data_dir))

    app = FastAPI()
    app.include_router(receipts_router)
    client = TestClient(app)

    r = client.get(f"/v1/receipts/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["oml_cid"] == cid
    assert body["ope"] == "sig"
    assert client.get(f"/v1/receipts/{cid}").headers.get("ETag")


def test_get_receipt_404(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "odin"))
    app = FastAPI()
    app.include_router(receipts_router)
    client = TestClient(app)

    r = client.get("/v1/receipts/not-found")
    assert r.status_code == 404
