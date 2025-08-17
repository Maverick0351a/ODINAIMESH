# path: libs/odin_core/tests/test_ope_integration.py
from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.gateway.odin_gateway.api_gateway import app
from odin.ope import verify_over_content
from odin.oml import compute_cid


def test_ope_integration_roundtrip(tmp_path, monkeypatch):
    # Ensure files write to temp dir
    monkeypatch.chdir(tmp_path)

    client = TestClient(app)
    r = client.post("/v1/translate", json={"text": "ciao", "source_lang": "it", "target_lang": "en"})
    assert r.status_code == 200

    cid = r.headers["X-ODIN-OML-CID"]
    path = Path(r.headers["X-ODIN-OML-C-Path"])
    assert path.exists()

    # Parse OPE from header
    ope_b64 = r.headers["X-ODIN-OPE"]
    ope = json.loads(base64.b64decode(ope_b64).decode("utf-8"))

    oml_bytes = path.read_bytes()
    # expected CID matches file contents
    assert compute_cid(oml_bytes) == cid

    ok = verify_over_content(ope, oml_bytes, expected_oml_cid=cid)
    assert ok["ok"] is True

    # Tamper -> should fail
    bad = verify_over_content(ope, oml_bytes + b" ", expected_oml_cid=cid)
    assert bad["ok"] is False
