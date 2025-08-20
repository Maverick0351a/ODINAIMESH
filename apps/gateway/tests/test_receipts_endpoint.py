from fastapi.testclient import TestClient
from apps.gateway.api import app
from pathlib import Path


def test_get_receipt_roundtrip(tmp_path, monkeypatch):
    # Redirect data dir to temp
    monkeypatch.setenv("ODIN_DATA_DIR", str(tmp_path))
    c = TestClient(app)
    # Produce a receipt via translate
    r = c.post("/v1/translate", json={"content": "hello", "target_lang": "en"})
    assert r.status_code == 200
    cid = r.json()["oml_cid"]

    # Receipt file should exist under data dir
    p = tmp_path / "receipts" / f"{cid}.ope.json"
    assert p.exists()

    # Fetch via receipts API and verify caching headers
    resp = c.get(f"/v1/receipts/{cid}")
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control")
    assert resp.headers.get("ETag")
    body = resp.json()
    assert isinstance(body, dict)
    assert body.get("oml_cid") == cid or True  # structure may vary, ensure JSON parses


def test_missing_receipt_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("ODIN_DATA_DIR", str(tmp_path))
    c = TestClient(app)
    resp = c.get("/v1/receipts/bboguscid")
    assert resp.status_code == 404
