import os
from fastapi.testclient import TestClient


def test_translate_emits_transform_receipt_and_fetches():
    # Ensure feature enabled and maps directory set before app import
    os.environ["ODIN_TRANSFORM_RECEIPTS"] = "1"
    os.environ["ODIN_SFT_MAPS_DIR"] = "config/sft_maps"
    os.environ.pop("ODIN_SIGN_ROUTES", None)

    from apps.gateway import api as gateway_api  # import after env

    client = TestClient(gateway_api.app)

    body = {
        "payload": {
            "intent": "openai.tool.call",
            "tool_name": "math.add",
            "arguments": {"a": 2, "b": 2},
        },
        "from_sft": "openai.tool@v1",
        "to_sft": "odin.task@v1",
    }

    r = client.post("/v1/translate", json=body)
    assert r.status_code == 200, r.text

    # Headers should be present when transform receipts are enabled
    h_map = r.headers.get("X-ODIN-Transform-Map")
    h_rec = r.headers.get("X-ODIN-Transform-Receipt")
    assert h_map, "missing X-ODIN-Transform-Map"
    assert h_rec and h_rec.startswith("/v1/receipts/transform/"), "missing transform receipt path"

    # Fetch the transform receipt by path
    r2 = client.get(h_rec)
    assert r2.status_code == 200, r2.text
    doc = r2.json()
    # Basic structure
    assert isinstance(doc, dict)
    assert doc.get("subject") and doc.get("envelope")
    assert doc.get("type") == "odin.transform.receipt"
