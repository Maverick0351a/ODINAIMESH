from __future__ import annotations

import json
from fastapi.testclient import TestClient

def test_bridge_env_target_override(monkeypatch):
    # Enable outbound signing and set env-based Beta base URL
    monkeypatch.setenv("ODIN_BRIDGE_HTTP_SIG", "1")
    monkeypatch.setenv("ODIN_BETA_URL", "https://beta.example.test")

    from apps.gateway import api as gateway_api

    # Capture the URL used by AsyncClient.post and default headers from constructor
    called = {"url": None, "body": None, "headers": None}

    class _FakeResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "application/json"}
        def raise_for_status(self): return None
        def json(self): return {"intent": "beta.reply", "output": "4", "success": True}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            # httpx.AsyncClient default headers are provided at construction
            called["headers"] = kwargs.get("headers") or {}
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def post(self, url, json=None, data=None, headers=None):
            called["url"] = url
            called["body"] = data if data is not None else json
            # If per-call headers passed, prefer those; otherwise keep constructor headers
            if headers is not None:
                called["headers"] = headers
            return _FakeResp()

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "AsyncClient", _FakeAsyncClient)

    client = TestClient(gateway_api.app)
    body = {
        "payload": {
            "intent": "openai.tool.call",
            "tool_name": "math.add",
            "arguments": {"a": 2, "b": 2},
        }
    }
    r = client.post("/v1/bridge/openai", json=body)
    assert r.status_code == 200, r.text

    # Ensure we POSTed to env-based Cloud Run URL + /task
    assert called["url"] == "https://beta.example.test/task"
    # Signature header should be present (bridge signs when ODIN_BRIDGE_HTTP_SIG=1)
    assert "X-ODIN-HTTP-Signature" in (called["headers"] or {})
