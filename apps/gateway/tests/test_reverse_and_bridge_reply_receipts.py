from fastapi.testclient import TestClient
import json
import os
import types


def test_reverse_translate_receipt():
    """
    Exercise the reverse transform path by calling /v1/translate with a Beta->Alpha map.
    Expect transform receipt persisted and headers present.
    """
    os.environ["ODIN_SFT_MAPS_DIR"] = "config/sft_maps"
    os.environ["ODIN_TRANSFORM_RECEIPTS"] = "1"

    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    body = {
        "payload": {"intent": "beta.reply", "output": "4", "success": True},
        "from_sft": "beta@v1",
        "to_sft": "alpha@v1",
    }
    r = client.post("/v1/translate", json=body)
    assert r.status_code == 200, r.text

    # Headers
    m = r.headers.get("X-ODIN-Transform-Map")
    assert m in ("beta@v1__alpha@v1", "beta@v1→alpha@v1")
    key = r.headers.get("X-ODIN-Transform-Receipt")
    url = r.headers.get("X-ODIN-Transform-Receipt-URL")
    assert key and key.startswith("receipts/transform/")
    assert url and url.startswith("/v1/receipts/transform/")

    # GET the receipt
    r2 = client.get(url)
    assert r2.status_code == 200
    assert r2.headers.get("ETag")
    data = r2.json()
    assert data["to_sft"] == "alpha@v1"
    assert data["stage"] in ("reverse", "translate", "bridge.reply", "task->beta")  # tolerant across impls


def test_bridge_openai_reply_stage_receipt(monkeypatch):
    """
    Bridge end-to-end (without external server) using a stubbed AsyncClient.
    Expect reply-stage transform receipt headers and endpoint retrieval.
    """
    os.environ["ODIN_SFT_MAPS_DIR"] = "config/sft_maps"
    os.environ["ODIN_TRANSFORM_RECEIPTS"] = "1"

    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    # Stub Agent Beta call (httpx.AsyncClient.post)
    class _FakeResp:
        def __init__(self):
            self.headers = {"content-type": "application/json"}
            self.status_code = 200
        def raise_for_status(self): return None
        def json(self): return {"intent": "beta.reply", "output": "4", "success": True}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def post(self, url, json): return _FakeResp()

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "AsyncClient", _FakeAsyncClient)

    body = {
        "payload": {
            "intent": "openai.tool.call",
            "tool_name": "math.add",
            "arguments": {"a": 2, "b": 2},
        }
    }
    r = client.post("/v1/bridge/openai", json=body)
    assert r.status_code == 200, r.text

    # Headers must be present
    m = r.headers.get("X-ODIN-Transform-Map")
    assert m in ("beta@v1__alpha@v1", "beta@v1→alpha@v1")
    key = r.headers.get("X-ODIN-Transform-Receipt")
    url = r.headers.get("X-ODIN-Transform-Receipt-URL")
    assert key and key.startswith("receipts/transform/")
    assert url and url.startswith("/v1/receipts/transform/")

    # Receipt must be fetchable
    r2 = client.get(url)
    assert r2.status_code == 200, r2.text
    doc = r2.json()
    assert doc["stage"] == "bridge.reply"
    assert doc["to_sft"] == "alpha@v1"
