from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Dict, Any, List, Optional, Tuple
import os, time
from libs.odin_core.odin.sft_discovery import validate_service_advert

services_router = APIRouter()

_DEFAULT_TTL_S = int(os.environ.get("ODIN_SERVICES_DEFAULT_TTL_S", "600"))
_MAX_TTL_S = int(os.environ.get("ODIN_SERVICES_MAX_TTL_S", "3600"))
# Registry: id -> (record, expire_epoch_s)
_REG: Dict[str, Tuple[Dict[str, Any], float]] = {}

def _now_s() -> float:
    return time.time()

def _cap_ttl(ttl_s: Optional[int]) -> int:
    if ttl_s is None:
        return _DEFAULT_TTL_S
    ttl = max(1, int(ttl_s))
    return min(ttl, _MAX_TTL_S)

def _gc() -> None:
    t = _now_s()
    dead = [sid for sid, (_, exp) in _REG.items() if exp <= t]
    for sid in dead:
        _REG.pop(sid, None)

@services_router.post("/v1/services/register")
def register_service(body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    # Validate minimal discovery SFT (no cryptographic verification here)
    violations = validate_service_advert(body)
    if violations:
        raise HTTPException(status_code=422, detail={"error": "odin.sft.invalid", "violations": violations})

    sid = body["id"].strip()
    ttl = _cap_ttl(body.get("ttl_s"))
    expires_at = _now_s() + ttl

    # Normalize a few fields (cheap hygiene)
    body = dict(body)
    body["tags"] = sorted(set(body.get("tags", []) or []))
    body["intents"] = sorted(set(body.get("intents", []) or []))
    body["registered_at_s"] = _now_s()
    body["ttl_s"] = ttl
    body["expires_at_s"] = expires_at

    _REG[sid] = (body, expires_at)
    _gc()

    return {"ok": True, "id": sid, "ttl_s": ttl, "expires_at_s": expires_at}

@services_router.get("/v1/services")
def list_services(
    intent: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    _gc()
    out: List[Dict[str, Any]] = []
    for record, exp in _REG.values():
        if intent and intent not in record.get("intents", []):
            continue
        if tag and tag not in (record.get("tags") or []):
            continue
        out.append(record)
    out.sort(key=lambda r: r.get("name", ""))
    return {"count": len(out), "services": out}

@services_router.get("/v1/services/{sid}")
def get_service(sid: str) -> Dict[str, Any]:
    _gc()
    item = _REG.get(sid)
    if not item:
        raise HTTPException(status_code=404, detail="service not found")
    return item[0]
