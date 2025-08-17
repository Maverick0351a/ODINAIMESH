from fastapi.testclient import TestClient
from apps.gateway.api import app
from pathlib import Path
import os


def test_translate_builds_oml_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("ODIN_TMP_DIR", str(tmp_path))
    c = TestClient(app)
    r = c.post("/v1/translate", json={"content":"hola", "source_lang":"es", "target_lang":"en"})
    assert r.status_code == 200
    data = r.json()
    cid = data["oml_cid"]
    p = Path(data["oml_path"])
    assert cid.startswith("b")
    assert p.exists() and p.read_bytes()  # bytes persisted
