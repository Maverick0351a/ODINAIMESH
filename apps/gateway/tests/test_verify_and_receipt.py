from fastapi.testclient import TestClient
from apps.gateway.api import app
from pathlib import Path
import base64
import orjson


def test_verify_inline_and_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("ODIN_TMP_DIR", str(tmp_path))
    c = TestClient(app)
    r = c.post("/v1/translate", json={"content": "hola", "source_lang": "es", "target_lang": "en"})
    assert r.status_code == 200
    cid = r.headers["X-ODIN-OML-CID"]
    p = Path(r.json()["oml_path"])  # file exists
    receipt = Path(r.json()["receipt_path"])  # receipt exists
    assert p.exists() and receipt.exists()

    b = p.read_bytes()
    ope_b64 = r.headers["X-ODIN-OPE"]
    ope = orjson.loads(base64.b64decode(ope_b64))

    # Inline verify
    body = {
        "ope": ope,
        "cid": cid,
        "bytes_b64": base64.b64encode(b).decode("ascii"),
    }
    rv = c.post("/v1/verify", json=body)
    assert rv.status_code == 200
    assert rv.json().get("ok") is True

    # Bad CID should fail
    body["cid"] = "b" + "a" * 52
    rv2 = c.post("/v1/verify", json=body)
    assert rv2.status_code == 200
    assert rv2.json().get("ok") is False
