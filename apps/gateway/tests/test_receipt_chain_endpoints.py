from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gateway.receipts import router as receipts_router
from apps.gateway.relay_mesh import mesh_router


def test_hop_chain_list_and_get(monkeypatch, tmp_path):
    # Use in-memory storage
    monkeypatch.setenv("ODIN_STORAGE_BACKEND", "inmem")

    app = FastAPI()
    app.include_router(mesh_router)
    app.include_router(receipts_router)
    c = TestClient(app)

    # First hop: no outbound
    r1 = c.post("/v1/mesh/forward", json={"payload": {"a": 1}})
    assert r1.status_code == 200
    trace_id = r1.headers.get("X-ODIN-Trace-Id")
    hop1 = r1.headers.get("X-ODIN-Hop-Id")
    assert trace_id and hop1 and hop1.startswith(trace_id + "-")

    # Second hop: continue same trace and forwarded_by
    headers = {
        "X-ODIN-Trace-Id": trace_id,
        "X-ODIN-Forwarded-By": r1.headers.get("X-ODIN-Forwarded-By", ""),
    }
    r2 = c.post("/v1/mesh/forward", headers=headers, json={"payload": {"b": 2}})
    assert r2.status_code == 200
    hop2 = r2.headers.get("X-ODIN-Hop-Id")
    assert hop2 and hop2.startswith(trace_id + "-") and hop2 != hop1

    # List hops for trace
    rl = c.get(f"/v1/receipts/hops", params={"trace_id": trace_id})
    assert rl.status_code == 200
    body = rl.json()
    items = body.get("items", [])
    assert len(items) >= 2

    # Get full chain
    rc = c.get(f"/v1/receipts/chain/{trace_id}")
    assert rc.status_code == 200
    chain = rc.json()
    assert chain.get("trace_id") == trace_id
    hops = chain.get("hops", [])
    assert len(hops) >= 2
    # Ensure hop ordering asc
    hop_nums = [h.get("hop") or h.get("hop_no") for h in hops]
    assert hop_nums == sorted(hop_nums)
