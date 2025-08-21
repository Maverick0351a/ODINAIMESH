from __future__ import annotations

import time
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from libs.odin_core.odin.ledger import create_ledger_from_env


router = APIRouter()


class LedgerAppendIn(BaseModel):
    cid: str
    meta: dict | None = None


@router.post("/v1/ledger/append")
def ledger_append(body: LedgerAppendIn):
    # Basic CID sanity: ODIN base32 CIDs start with 'b'
    if not isinstance(body.cid, str) or not body.cid.startswith("b"):
        raise HTTPException(status_code=400, detail="invalid cid")
    entry = {"ts_ns": time.time_ns(), "cid": body.cid, "meta": body.meta or {}}
    led = create_ledger_from_env()
    loc = led.append(entry)
    # Best-effort index (file backend only)
    idx = None
    try:
        if isinstance(loc, str) and loc.endswith("ledger.jsonl"):
            p = Path(loc)
            with p.open("r", encoding="utf-8") as f:
                idx = sum(1 for _ in f) - 1
    except Exception:
        idx = None
    return {"ok": True, **({"index": idx} if idx is not None else {}), "location": loc}


@router.get("/v1/ledger")
def ledger_list(limit: int = 100):
    led = create_ledger_from_env()
    items = led.query(limit=limit)
    return {"count": len(items), "items": items}
