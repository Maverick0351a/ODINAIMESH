from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request

from libs.odin_core.odin.registry import (
    RegistryError,
    normalize_advert,
    compute_expiry_ns,
    compute_record_id_from_ad_cid,
)
from libs.odin_core.odin.registry_store import create_registry_from_env
from libs.odin_core.odin.verifier import verify  # core verifier

router = APIRouter(prefix="/v1/registry", tags=["registry"])
_STORE = create_registry_from_env()


def _now_ns() -> int:
    return time.time_ns()


@router.post("/register")
async def register_service(req: Request, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Accepts { payload, proof } where:
      - payload: odin.service.advertise object
      - proof:   ProofEnvelope over the exact JSON bytes of payload
    Verifies the proof and persists the record.
    """
    payload = body.get("payload")
    proof = body.get("proof")
    if not isinstance(payload, dict) or not isinstance(proof, dict):
        raise HTTPException(status_code=400, detail="body must be JSON {payload, proof}")

    try:
        ad = normalize_advert(payload)
    except RegistryError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Verify envelope against the provided payload using the core verifier.
    v = verify(
        oml_c_obj=ad,
        envelope=proof,
        # Let verifier resolve JWKS from envelope if present; no explicit jwks/jwks_url args
    )
    if not v.ok:
        raise HTTPException(status_code=401, detail={"error": "odin.proof.invalid", "message": v.reason or "invalid proof"})

    ad_cid = v.cid or proof.get("oml_cid")
    if not ad_cid:
        raise HTTPException(status_code=400, detail="missing oml_cid in verification/envelope")

    service_id = compute_record_id_from_ad_cid(ad_cid)
    now_ns = _now_ns()
    exp_ns = compute_expiry_ns(int(ad.get("ttl_s", 0) or 0)) if ad.get("ttl_s") else 0

    doc = {
        "id": service_id,
        "service": ad["service"],
        "version": ad.get("version") or "",
        "base_url": ad["base_url"],
        "sft": list(ad.get("sft") or []),
        "labels": dict(ad.get("labels") or {}),
        "endpoints": dict(ad.get("endpoints") or {}),
        "ad_cid": ad_cid,
        "owner_kid": v.kid,
        "created_ts_ns": now_ns,
        "updated_ts_ns": now_ns,
        "expires_ts_ns": exp_ns,
        "payload": ad,
        "proof": proof,
    }

    _STORE.upsert(service_id, doc)

    return {
        "ok": True,
        "id": service_id,
        "owner_kid": v.kid,
        "ad_cid": ad_cid,
        "expires_ts_ns": exp_ns,
    }


@router.get("/services")
async def list_services(
    service: Optional[str] = None,
    sft: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
) -> Dict[str, Any]:
    items = _STORE.list(
        service=service or None,
        sft=sft or None,
        active_only=bool(active_only),
        now_ns=_now_ns(),
        limit=min(max(limit, 1), 500),
    )
    # Return summary rows (omit heavy proof/payload)
    summaries = [
        {
            "id": d["id"],
            "service": d.get("service"),
            "version": d.get("version"),
            "base_url": d.get("base_url"),
            "sft": d.get("sft") or [],
            "labels": d.get("labels") or {},
            "expires_ts_ns": d.get("expires_ts_ns") or 0,
        }
        for d in items
    ]
    return {"count": len(summaries), "items": summaries}


@router.get("/services/{service_id}")
async def get_service(service_id: str) -> Dict[str, Any]:
    d = _STORE.get(service_id)
    if not d:
        raise HTTPException(status_code=404, detail="service not found")
    return d
