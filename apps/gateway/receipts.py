from __future__ import annotations

import hashlib
import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, Response

from libs.odin_core.odin.constants import DEFAULT_DATA_DIR, ENV_DATA_DIR
from libs.odin_core.odin.storage import create_storage_from_env, key_receipt

router = APIRouter()


def _data_dir() -> str:
    return os.getenv(ENV_DATA_DIR, DEFAULT_DATA_DIR)


def _receipt_path(cid: str) -> str:
    # Receipts persisted as tmp/odin/receipts/<cid>.ope.json
    return os.path.join(_data_dir(), "receipts", f"{cid}.ope.json")


def _weak_etag(data: bytes) -> str:
    return f'W/"{hashlib.sha256(data).hexdigest()}"'


@router.get("/v1/receipts/hops/{hop_id}")
def get_hop_receipt(hop_id: str):
    """
    Return a persisted hop receipt by id (format: <trace_id>-<hop_no>).
    """
    storage = create_storage_from_env()
    key = f"receipts/hops/{hop_id}.json"
    try:
        data = storage.get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="hop receipt not found")
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "ETag": _weak_etag(data),
            "Cache-Control": "public, max-age=31536000",
        },
    )


def _hop_key(trace_id: str | None = None, hop_id: str | None = None) -> str:
    if hop_id:
        return f"receipts/hops/{hop_id}.json"
    if trace_id:
        return f"receipts/hops/{trace_id}-"
    return "receipts/hops/"


def _parse_hop_no(hop_id: str) -> int:
    try:
        # hop_id format: <trace_id>-<hop_no>
        return int(hop_id.rsplit("-", 1)[-1])
    except Exception:
        return 0


@router.get("/v1/receipts/hops")
def list_hop_receipts(trace_id: str | None = None, expand: bool = False):
    """
    List hop receipts. When trace_id is provided, returns only hops for that trace.
    - expand=false (default): return lightweight items with id and URL
    - expand=true: return the full stored receipt documents
    """
    storage = create_storage_from_env()
    keys = list(storage.list("receipts/hops/"))
    items: list[dict] = []
    for key in keys:
        if not key.endswith(".json"):
            continue
        basename = key.split("/")[-1]
        hid = basename[:-5]
        if trace_id and not hid.startswith(f"{trace_id}-"):
            continue
        if expand:
            try:
                data = storage.get_bytes(key)
                obj = json.loads(data.decode("utf-8"))
            except Exception:
                obj = {"error": "unreadable"}
            items.append(obj)
        else:
            url = storage.url_for(key) or f"/v1/receipts/hops/{hid}"
            items.append({"hop_id": hid, "url": url})
    if trace_id:
        items.sort(key=lambda x: (x.get("hop") or x.get("hop_no") or _parse_hop_no(x.get("hop_id", ""))))
    else:
        items.sort(key=lambda x: x.get("hop_id", ""))
    try:
        etag_src = ",".join([i.get("hop_id") if isinstance(i, dict) else "" for i in items]).encode("utf-8")
        etag = _weak_etag(etag_src)
    except Exception:
        etag = None
    headers = {"Cache-Control": "public, max-age=60"}
    if etag:
        headers["ETag"] = etag
    return JSONResponse({"items": items, "count": len(items)}, headers=headers)


@router.get("/v1/receipts/chain/{trace_id}")
def get_receipt_chain(trace_id: str, tenant: str | None = None):
    """
    Return the assembled hop chain for a given trace id, ordered by hop number.
    """
    storage = create_storage_from_env()
    keys = [k for k in storage.list("receipts/hops/") if k.endswith(".json")]
    hops: list[dict] = []
    for key in keys:
        basename = key.split("/")[-1]
        hid = basename[:-5]
        if not hid.startswith(f"{trace_id}-"):
            continue
        try:
            data = storage.get_bytes(key)
            obj = json.loads(data.decode("utf-8"))
            if tenant and obj.get("tenant") != tenant:
                continue
            hops.append(obj)
        except Exception:
            # Skip unreadable entries
            continue
    if not hops:
        raise HTTPException(status_code=404, detail="trace not found")
    hops.sort(key=lambda h: h.get("hop") or h.get("hop_no") or _parse_hop_no(str(h.get("hop_id", ""))))
    return JSONResponse(
        {"trace_id": trace_id, "length": len(hops), "hops": hops},
        headers={"Cache-Control": "public, max-age=60"},
    )


# Alias path to match discovery/clients expecting '/v1/receipts/hops/chain/{trace_id}'
@router.get("/v1/receipts/hops/chain/{trace_id}")
def get_receipt_chain_alias(trace_id: str):
    return get_receipt_chain(trace_id)


# Keep this dynamic route last to avoid shadowing more specific '/v1/receipts/hops*' routes
@router.get("/v1/receipts/{cid}", tags=["receipts"])
async def get_receipt(cid: str):
    # Optional redirect to storage URL if available
    redirect = os.getenv("ODIN_RECEIPTS_REDIRECT", "0").lower() in ("1", "true", "yes")
    storage = create_storage_from_env()
    if redirect:
        try:
            url = storage.url_for(key_receipt(cid))
        except Exception:
            url = None
        if url:
            return RedirectResponse(url, status_code=302)

    path = _receipt_path(cid)
    raw: bytes
    if os.path.isfile(path):
        with open(path, "rb") as f:
            raw = f.read()
    else:
        # Fallback to storage backend
        key = key_receipt(cid)
        try:
            if not storage.exists(key):
                raise HTTPException(status_code=404, detail="receipt not found")
            raw = storage.get_bytes(key)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="receipt not found")

    # Best-effort JSON parse; if corrupt, expose as 500
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="stored receipt is invalid")

    # Strong ETag for immutability; year-long cache is safe for content-addressed receipts
    etag = hashlib.sha256(raw).hexdigest()
    return JSONResponse(
        data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{etag}"',
        },
    )
