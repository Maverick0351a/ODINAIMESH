import os, json
from fastapi.testclient import TestClient
import types

def test_mesh_forward_envelope_hop_receipt(monkeypatch):
    # Router A client
    from apps.gateway import api as gateway_api
    monkeypatch.setenv("ODIN_ROUTER_ID", "routerA")
    clientA = TestClient(gateway_api.app)

    # Router B client (same app instance, but we'll flip the env per-call)
    clientB = TestClient(gateway_api.app)

    # Patch httpx.AsyncClient to route to our in-process Router B
    import httpx as _httpx

    class _Resp:
        def __init__(self, r):
            self._r = r
            self.status_code = r.status_code
            self.headers = dict(r.headers)

        def json(self):
            return self._r.json()

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            # Force B identity for this nested call
            prev = os.environ.get("ODIN_ROUTER_ID")
            os.environ["ODIN_ROUTER_ID"] = "routerB"
            try:
                # We only exercise /v1/envelope for now
                assert url.endswith("/v1/envelope")
                r = clientB.post("/v1/envelope", json=json)
                return _Resp(r)
            finally:
                if prev is None:
                    del os.environ["ODIN_ROUTER_ID"]
                else:
                    os.environ["ODIN_ROUTER_ID"] = prev

    monkeypatch.setattr(_httpx, "AsyncClient", _FakeAsyncClient)

    # Call mesh forward on A → B:/v1/envelope
    body = {"target_url": "http://routerB/v1/envelope", "payload": {"hello": "world"}}
    r = clientA.post("/v1/mesh/forward", json=body)
    assert r.status_code == 200, r.text
    assert r.headers.get("X-ODIN-Trace-Id")
    assert r.headers.get("X-ODIN-Forwarded-By") == "routerA"
    assert r.headers.get("X-ODIN-Receipt-Chain").endswith(":1")

    # The downstream response should be an envelope-shaped JSON
    j = r.json()
    assert "proof" in j and isinstance(j["proof"], dict)
    assert j["proof"].get("oml_cid")

    # Hop receipt should exist and be fetchable
    href = r.headers.get("X-ODIN-Hop-Receipt-URL")
    assert href and href.startswith("/v1/receipts/hops/")
    r2 = clientA.get(href)
    assert r2.status_code == 200, r2.text
    rec = r2.json()
    assert rec["hop"] == 1
    assert rec["from"] == "routerA"
    assert rec["to_url"] == "http://routerB/v1/envelope"
    assert rec["out"]["proof"]["oml_cid"] == j["proof"]["oml_cid"]


def test_mesh_forward_chain_increments(monkeypatch):
    from apps.gateway import api as gateway_api
    monkeypatch.setenv("ODIN_ROUTER_ID", "routerA")
    clientA = TestClient(gateway_api.app)
    clientB = TestClient(gateway_api.app)

    import httpx as _httpx
    class _Resp:  # minimal wrapper
        def __init__(self, r):
            self._r = r
            self.status_code = r.status_code
            self.headers = dict(r.headers)
        def json(self): return self._r.json()

    class _FakeAsyncClient:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def post(self, url, json=None, headers=None):
            os.environ["ODIN_ROUTER_ID"] = "routerB"
            r = clientB.post("/v1/envelope", json=json)
            return _Resp(r)

    monkeypatch.setattr(__import__("httpx"), "AsyncClient", _FakeAsyncClient)

    # Provide incoming chain and trace id
    hdrs = {"X-ODIN-Forwarded-By": "routerX", "X-ODIN-Trace-Id": "trace-abc123"}
    r = clientA.post(
        "/v1/mesh/forward",
        json={"target_url": "http://routerB/v1/envelope", "payload": {"hello": "mesh"}},
        headers=hdrs,
    )
    assert r.status_code == 200
    # Chain must append 'routerA'
    assert r.headers.get("X-ODIN-Forwarded-By") == "routerX,routerA"
    # Hop number should be 2
    assert r.headers.get("X-ODIN-Receipt-Chain") == "trace-abc123:2"
