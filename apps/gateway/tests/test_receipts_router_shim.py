import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routers.receipts import router as receipts_router
from gateway.constants import ENV_DATA_DIR


def test_receipts_router_shim(tmp_path, monkeypatch):
    data_dir = tmp_path / "odin"
    receipts_dir = data_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    cid = "bafkqaaa-shim"
    (receipts_dir / f"{cid}.ope.json").write_text(json.dumps({"oml_cid": cid}), encoding="utf-8")

    monkeypatch.setenv(ENV_DATA_DIR, str(data_dir))
    app = FastAPI()
    app.include_router(receipts_router)
    c = TestClient(app)
    r = c.get(f"/v1/receipts/{cid}")
    assert r.status_code == 200
    assert r.json()["oml_cid"] == cid
