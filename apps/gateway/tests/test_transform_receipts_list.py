import json
from fastapi.testclient import TestClient

def test_transform_receipts_list_and_fetch(monkeypatch, tmp_path):
    # Ensure transform receipts are enabled and maps dir is set
    monkeypatch.setenv("ODIN_TRANSFORM_RECEIPTS", "1")
    monkeypatch.setenv("ODIN_SFT_MAPS_DIR", "config/sft_maps")

    # Boot the app
    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    # 1) Create a receipt via map mode translate (alpha -> beta)
    body = {
        # Per config/sft_maps/alpha@v1__beta@v1.json: alpha.ask -> beta.request; fields ask->prompt, reason->why
        "payload": {"intent": "alpha.ask", "ask": "2+2?", "reason": "demo"},
        "from_sft": "alpha@v1",
        "to_sft": "beta@v1",
    }
    r = client.post("/v1/translate", json=body)
    assert r.status_code == 200, r.text
    key = r.headers.get("X-ODIN-Transform-Receipt")
    url = r.headers.get("X-ODIN-Transform-Receipt-URL")
    assert key and key.startswith("receipts/transform/")
    assert url and url.startswith("/v1/receipts/transform/")

    # 2) List with map filter should include this receipt
    r2 = client.get("/v1/receipts/transform", params={"map": "alpha@v1__beta@v1", "limit": 10})
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["count"] >= 1
    items = data["items"]
    found = next((it for it in items if it["receipt_url"] == url), None)
    assert found, f"did not find {url} in {items}"

    # 3) Fetch the receipt by URL and correlate
    r3 = client.get(url)
    assert r3.status_code == 200, r3.text
    rec = r3.json()
    assert rec.get("v") == 1
    assert rec.get("out_cid") == found["out_cid"]

    # 4) Prefix filter
    prefix = found["out_cid"][:8]
    r4 = client.get("/v1/receipts/transform", params={"cid_prefix": prefix})
    assert r4.status_code == 200
    assert any(it["out_cid"].startswith(prefix) for it in r4.json()["items"])
