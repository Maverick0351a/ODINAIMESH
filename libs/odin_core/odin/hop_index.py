from __future__ import annotations

import os
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

try:
    # Optional FastAPI dependencies for router exposure
    from fastapi import APIRouter, HTTPException, Query  # type: ignore
    from pydantic import BaseModel, Field  # type: ignore
except Exception:  # pragma: no cover
    APIRouter = None  # type: ignore
    HTTPException = Exception  # type: ignore
    Query = lambda *a, **k: None  # type: ignore
    class BaseModel:  # type: ignore
        pass
    def Field(*a, **k):  # type: ignore
        return None

log = logging.getLogger("odin.hops")

# ----- Firestore (optional) -----
FS_ENABLED = os.getenv("HOP_INDEX_ENABLE_FIRESTORE", "1") == "1"
_fs = None
if FS_ENABLED:
    try:
        from google.cloud import firestore  # type: ignore

        _fs = firestore.Client()
    except Exception as e:  # pragma: no cover - optional dependency
        log.warning("Firestore unavailable; hop index will be memory-only (%s)", e)
        _fs = None


# ----- Models -----

class HopReceipt(BaseModel):  # type: ignore[misc]
    trace_id: str = Field(..., description="Route trace id")
    hop: int = Field(..., ge=0, description="Hop ordinal")
    in_cid: str = Field(..., description="Input CID")
    out_cid: str = Field(..., description="Output CID")
    signer: Optional[str] = None
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: Optional[dict] = None


# ----- In-memory index -----
_INDEX: Dict[str, List[HopReceipt]] = defaultdict(list)


def _fs_key(trace_id: str, hop: int) -> Tuple[str, str]:
    return ("hop_index", f"{trace_id}:{hop:05d}")


def record_hop(receipt: HopReceipt) -> None:
    # memory
    hops = _INDEX[receipt.trace_id]
    hops.append(receipt)
    # persist (best-effort)
    if _fs is not None:
        col, key = _fs_key(receipt.trace_id, receipt.hop)
        try:
            _fs.collection(col).document(key).set(receipt.model_dump())
        except Exception as e:  # pragma: no cover - best-effort
            log.warning("Failed to persist hop to Firestore: %s", e)


def sorted_hops(trace_id: str) -> List[HopReceipt]:
    hops = list(_INDEX.get(trace_id, []))
    hops.sort(key=lambda r: (r.hop, getattr(r, "at", datetime.now(timezone.utc))))
    return hops


def ensure_backfill(trace_id: str) -> None:
    """If memory index is empty and Firestore exists, try to backfill a page (best-effort)."""
    if _fs is None:
        return
    if _INDEX.get(trace_id):
        return
    try:
        col = _fs.collection("hop_index").where("trace_id", "==", trace_id).stream()
        for doc in col:
            try:
                _INDEX[trace_id].append(HopReceipt(**doc.to_dict()))
            except Exception:
                continue
    except Exception as e:  # pragma: no cover
        log.warning("Failed to backfill from Firestore: %s", e)


def continuity(hops: List[HopReceipt]) -> Tuple[bool, List[int], List[int]]:
    """Returns (ok, missing_hops, mismatch_positions)."""
    missing: List[int] = []
    mismatch: List[int] = []
    if not hops:
        return False, [], []
    # Detect missing hop numbers
    expected = list(range(hops[0].hop, hops[0].hop + len(hops)))
    actual = [h.hop for h in hops]
    for n in expected:
        if n not in actual:
            missing.append(n)
    # CID continuity
    for i in range(len(hops) - 1):
        if hops[i].out_cid != hops[i + 1].in_cid:
            mismatch.append(i)
    ok = (len(missing) == 0) and (len(mismatch) == 0)
    return ok, missing, mismatch


# ----- Optional API Router (not auto-included) -----
if APIRouter is not None:  # pragma: no cover - exercised in integration
    router = APIRouter(prefix="/v1/receipts/hops", tags=["receipts"])  # type: ignore

    @router.get("")
    def list_hops(trace_id: str = Query(..., description="Trace identifier")):  # type: ignore
        ensure_backfill(trace_id)
        hops = sorted_hops(trace_id)
        return {
            "trace_id": trace_id,
            "count": len(hops),
            "items": [h.model_dump() for h in hops],
        }

    @router.get("/chain/{trace_id}")
    def hop_chain(trace_id: str):  # type: ignore
        ensure_backfill(trace_id)
        hops = sorted_hops(trace_id)
        if not hops:
            # FastAPI's HTTPException if available; else generic
            if isinstance(HTTPException, type):
                raise HTTPException(status_code=404, detail="no hops recorded for trace_id")  # type: ignore
            raise Exception("no hops recorded for trace_id")
        ok, missing, mismatch = continuity(hops)
        return {
            "trace_id": trace_id,
            "count": len(hops),
            "ordered": [h.model_dump() for h in hops],
            "continuity_ok": ok,
            "missing_hops": missing,
            "cid_mismatches_at": mismatch,
        }


__all__ = [
    "HopReceipt",
    "record_hop",
    "sorted_hops",
    "ensure_backfill",
    "continuity",
]
