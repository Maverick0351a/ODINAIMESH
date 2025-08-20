from fastapi.testclient import TestClient
import json

def test_bridge_emits_metrics(monkeypatch):
    from apps.gateway import api as gateway_api

    # Stub Beta hop to succeed
    class _FakeResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "application/json"}
        def raise_for_status(self):
            return None
        def json(self):
            return {"intent": "beta.reply", "output": "4", "success": True}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, a, b, c):
            return False
        async def post(self, url, data=None, json=None, headers=None):
            return _FakeResp()

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "AsyncClient", _FakeAsyncClient)

    client = TestClient(gateway_api.app)
    body = {"payload": {"intent": "openai.tool.call", "tool_name": "math.add", "arguments": {"a": 2, "b": 2}}}
    r = client.post("/v1/bridge/openai", json=body)
    assert r.status_code == 200

    metrics = client.get("/metrics").text
    # Request/latency families should be present
    assert "odin_http_requests_total" in metrics
    assert "odin_http_request_seconds_bucket" in metrics
    # Bridge hop metrics should record at least one 'ok' request and latency buckets
    assert 'odin_bridge_beta_requests_total{outcome="ok"}' in metrics
    assert "odin_bridge_beta_request_seconds_bucket" in metrics
