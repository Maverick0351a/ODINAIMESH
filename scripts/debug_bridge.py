from fastapi.testclient import TestClient
from apps.gateway import api as gateway_api
import httpx as _httpx

class _FakeResp:
    def __init__(self):
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self.text = '{"intent":"beta.reply","output":"4","success":true}'
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

# monkeypatch
_httpx.AsyncClient = _FakeAsyncClient

client = TestClient(gateway_api.app)
body = {"payload": {"intent": "openai.tool.call", "tool_name": "math.add", "arguments": {"a": 2, "b": 2}}}
r = client.post("/v1/bridge/openai", json=body)
print("status:", r.status_code)
print("body:", r.text)
