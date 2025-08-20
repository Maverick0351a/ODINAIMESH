from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


DISCOVERY_PATH = "/.well-known/odin/discovery.json"


def discovery_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}{DISCOVERY_PATH}"


@dataclass
class Discovery:
    jwks_url: str
    endpoints: Dict[str, str]
    policy: Dict[str, Any]
    protocol: Dict[str, Any]
    raw: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Discovery":
        # Prefer explicit jwks_url; fall back to endpoints.jwks
        jwks = data.get("jwks_url") or (data.get("endpoints", {}) or {}).get("jwks")
        if not jwks:
            raise ValueError("discovery: missing jwks_url")
        return cls(
            jwks_url=jwks,
            endpoints=data.get("endpoints", {}) or {},
            policy=data.get("policy", {}) or {},
            protocol=data.get("protocol", {}) or {},
            raw=data,
        )


def fetch_discovery(
    base_url: str,
    *,
    transport: Optional[httpx.BaseTransport] = None,
    timeout: float = 10.0,
) -> Discovery:
    url = discovery_url(base_url)
    with httpx.Client(transport=transport, timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return Discovery.from_dict(r.json())
