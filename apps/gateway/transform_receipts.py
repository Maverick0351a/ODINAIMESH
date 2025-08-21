from __future__ import annotations

import hashlib
import json
import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse

from libs.odin_core.odin.constants import ENV_DATA_DIR, DEFAULT_DATA_DIR
from libs.odin_core.odin.storage import create_storage_from_env, key_transform_receipt, cache_transform_receipt_get
from libs.odin_core.odin.ledger import create_ledger_from_env


router = APIRouter()
# Exported alias so callers can `from apps.gateway.transform_receipts import transform_receipts_router`
transform_receipts_router = router


def _data_dir() -> str:
    return os.getenv(ENV_DATA_DIR, DEFAULT_DATA_DIR)


def _tr_path(cid: str) -> str:
    # Transform receipts persisted as tmp/odin/receipts/transform/<cid>.json
    return os.path.join(_data_dir(), "receipts", "transform", f"{cid}.json")


def _match_filters(ev: dict, m: str | None, cid_prefix: str | None, since: int | None) -> bool:
    if ev.get("kind") != "transform.receipt":
        return False
    if m and ev.get("map") != m:
        return False
    if cid_prefix and not str(ev.get("out_cid", "")).startswith(cid_prefix):
        return False
    if since and int(ev.get("ts_ns", 0)) < int(since):
        return False
    return True


@router.get("/v1/receipts/transform", tags=["receipts", "transform"])
def list_transform_receipts(
    map: str | None = Query(None, description="Filter by map name, e.g. alpha@v1__beta@v1"),
    cid_prefix: str | None = Query(None, description="Filter by out_cid prefix"),
    since: int | None = Query(None, description="Filter by minimum ts_ns (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
):
    """
    Returns recent transform receipts discovered via the Ledger index.
    Sorted by ts_ns DESC (most recent first).
    """
    ledger = create_ledger_from_env()
    # Pull a window larger than requested, then filter and trim.
    raw = ledger.list(limit=max(limit * 4, 200))  # small over-fetch to filter
    items: list[dict] = []

    for ev in raw:
        if _match_filters(ev, map, cid_prefix, since):
            items.append({
                "ts_ns": int(ev.get("ts_ns", 0)),
                "map": ev.get("map"),
                "stage": ev.get("stage"),
                "out_cid": ev.get("out_cid"),
                "in_cid": ev.get("in_cid"),
                "receipt_key": ev.get("receipt_key"),
                "receipt_url": ev.get("receipt_url"),
            })
            if len(items) >= limit:
                break

    # Ensure newest-first; file ledger may already be newest-first, but keep deterministic
    items.sort(key=lambda x: x["ts_ns"], reverse=True)
    return {"count": len(items), "items": items}


@router.get("/v1/receipts/transform/{out_cid}", tags=["receipts", "transform"])
async def get_transform_receipt(out_cid: str):
    # Optional redirect to storage URL if available
    redirect = os.getenv("ODIN_RECEIPTS_REDIRECT", "0").lower() in ("1", "true", "yes")
    storage = create_storage_from_env()
    if redirect:
        try:
            url = storage.url_for(key_transform_receipt(out_cid))
        except Exception:
            url = None
        if url:
            return RedirectResponse(url, status_code=302)

    # Try in-process cache first (useful in immediate follow-up fetches)
    cached = cache_transform_receipt_get(out_cid)
    if cached is not None:
        raw = cached
    else:
        path = _tr_path(out_cid)
        raw: bytes
        if os.path.isfile(path):
            with open(path, "rb") as f:
                raw = f.read()
        else:
            key = key_transform_receipt(out_cid)
            try:
                if not storage.exists(key):
                    raise HTTPException(status_code=404, detail="transform receipt not found")
                raw = storage.get_bytes(key)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=404, detail="transform receipt not found")

    # JSON parse with error handling
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="stored transform receipt is invalid")

    etag = hashlib.sha256(raw).hexdigest()
    return JSONResponse(
        data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{etag}"',
        },
    )
