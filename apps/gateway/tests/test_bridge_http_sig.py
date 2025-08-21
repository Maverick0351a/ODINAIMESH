from __future__ import annotations

from fastapi.testclient import TestClient


def test_bridge_adds_http_signature(monkeypatch):
    # Enable outbound HTTP signing on the bridge
    monkeypatch.setenv("ODIN_BRIDGE_HTTP_SIG", "1")

    from apps.gateway import api as gateway_api

    captured = {}

    class _FakeResp:
        def __init__(self):
            self.headers = {"content-type": "application/json"}
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"intent": "beta.reply", "output": "4", "success": True}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["default_headers"] = kwargs.get("headers")  # headers set at constructor

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
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
    assert r.status_code in (200, 502, 500)
    hdrs = captured.get("default_headers") or {}
    assert "X-ODIN-HTTP-Signature" in hdrs
    assert "X-ODIN-JWKS" in hdrs
