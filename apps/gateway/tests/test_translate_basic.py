# path: apps/gateway/tests/test_translate_basic.py
from fastapi.testclient import TestClient
from apps.gateway.odin_gateway.api_gateway import app
from pathlib import Path
from odin.oml import compute_cid


def test_translate_endpoint_persists_and_headers(tmp_path, monkeypatch):
    # Route tmp/oml to tmp_path/oml during test
    monkeypatch.chdir(tmp_path)

    client = TestClient(app)
    r = client.post("/v1/translate", json={"text": "Hello", "source_lang": "en", "target_lang": "fr"})
    assert r.status_code == 200
    data = r.json()
    cid = data["oml_cid"]

    # Headers present
    assert r.headers.get("X-ODIN-OML-CID") == cid
    p = r.headers.get("X-ODIN-OML-C-Path")
    assert p

    # File exists
    out = Path(p)
    assert out.exists() and out.is_file()

    # CID recomputable
    oml_bytes = out.read_bytes()
    cid2 = compute_cid(oml_bytes)
    assert cid2 == cid
