from fastapi.testclient import TestClient

def test_receipts_transform_get_roundtrip(tmp_path, monkeypatch):
    # Point storage to a temp dir and write a transform receipt, then fetch it via the API.
    from libs.odin_core.odin import storage as st

    monkeypatch.setenv("ODIN_DATA_DIR", str(tmp_path))
    s = st.create_storage_from_env()

    out_cid = "bd4qexamplecid"
    key = st.key_transform_receipt(out_cid)
    s.put_bytes(key, b'{"ok":true}', content_type="application/json")

    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    r = client.get(f"/v1/receipts/transform/{out_cid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
