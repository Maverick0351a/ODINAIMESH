from __future__ import annotations

# Simple SFT registry and re-exports for convenience
from .sft_core import (
    CORE_ID,
    load_sft,
    sft_info,
    validate,
    ValidationResult,
    ValidationError,
)

# Lightweight service advertisement helpers (optional; used by discovery/registry flows)
import time
from typing import Any, Dict, List

DEFAULT_TTL_S = 24 * 60 * 60  # 24h


class RegistryError(Exception):
    pass


def _now_ns() -> int:
    return time.time_ns()


def normalize_advert(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal schema check + normalization.
    Required:
      - intent == 'odin.service.advertise'
      - service: str
      - base_url: str
      - sft: list[str]
    Optional:
      - version: str
      - endpoints: dict[str, str]
      - labels: dict[str, str]
      - ttl_s: int (default 24h)
    """
    if not isinstance(payload, dict):
        raise RegistryError("payload must be an object")

    intent = payload.get("intent")
    if intent != "odin.service.advertise":
        raise RegistryError("invalid intent; expected 'odin.service.advertise'")

    service = payload.get("service")
    base_url = payload.get("base_url")
    sft = payload.get("sft", [])
    if not isinstance(service, str) or not service:
        raise RegistryError("field 'service' (str) required")
    if not isinstance(base_url, str) or not base_url:
        raise RegistryError("field 'base_url' (str) required")
    if not isinstance(sft, list):
        raise RegistryError("field 'sft' must be a list")

    ttl_s = payload.get("ttl_s", DEFAULT_TTL_S)
    try:
        ttl_s = int(ttl_s)
    except Exception:
        raise RegistryError("field 'ttl_s' must be int if present")

    labels = payload.get("labels") or {}
    endpoints = payload.get("endpoints") or {}
    version = payload.get("version") or ""

    return {
        **payload,
        "service": service,
        "base_url": base_url,
        "sft": list(sft),
        "ttl_s": ttl_s,
        "labels": dict(labels),
        "endpoints": dict(endpoints),
        "version": version,
    }


def compute_record_id_from_ad_cid(ad_cid: str) -> str:
    # Stable, deterministic ID derived from the advertisement CID.
    # Prefix for clarity; truncate to keep it readable.
    return "svc_" + (ad_cid or "")[:40]


def compute_expiry_ns(ttl_s: int) -> int:
    return _now_ns() + (int(ttl_s) * 1_000_000_000)


__all__ = [
    "CORE_ID",
    "load_sft",
    "sft_info",
    "validate",
    "ValidationResult",
    "ValidationError",
    # registry helpers
    "DEFAULT_TTL_S",
    "RegistryError",
    "_now_ns",
    "normalize_advert",
    "compute_record_id_from_ad_cid",
    "compute_expiry_ns",
]
