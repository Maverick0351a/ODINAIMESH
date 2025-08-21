from __future__ import annotations

import time
from typing import Any, Dict, Optional

from libs.odin_core.odin.ledger import create_ledger_from_env


def append_transform_index_event(
    *,
    out_cid: str,
    in_cid: Optional[str],
    map_name: str,
    stage: str,
    receipt_key: str,
    receipt_url: str,
    extra: Optional[Dict[str, Any]] = None,
    ts_ns: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Append a compact transform-receipt index record to the configured ledger.

    Fields:
    - kind: fixed "transform.receipt"
    - out_cid: output content identifier
    - in_cid: optional input content identifier
    - map: map name or id (e.g., "alpha@v1__beta@v1.json")
    - stage: human-friendly stage (e.g., "alpha→beta", "beta→alpha", or "bridge.reply")
    - receipt_key: storage key (receipts/transform/<out_cid>.json)
    - receipt_url: API path or absolute URL to retrieve the receipt
    - extra: optional additional fields
    - ts_ns: optional timestamp override (nanoseconds)
    """
    try:
        record = {
            "kind": "transform.receipt",
            "out_cid": out_cid,
            "in_cid": in_cid,
            "map": map_name,
            "stage": stage,
            "receipt_key": receipt_key,
            "receipt_url": receipt_url,
            "ts_ns": int(ts_ns or time.time_ns()),
        }
        if extra:
            record["extra"] = dict(extra)
        led = create_ledger_from_env()
        return led.append(record)
    except Exception:
        # Non-fatal: indexing should not block request handling
        return None


__all__ = ["append_transform_index_event"]
