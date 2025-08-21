from __future__ import annotations

import os
import threading
from typing import Dict, Tuple
import json
from pathlib import Path
from fastapi import Request
from starlette.responses import Response

try:
    # Optional metrics; fail open if not available
    from apps.gateway.metrics import (
        policy_violations_total as _pol,
        tenant_quota_consumed_total as _qcons,
        tenant_quota_blocked_total as _qblock,
    )
except Exception:  # pragma: no cover - metrics optional
    _pol = None
    _qcons = None
    _qblock = None

try:
    from libs.odin_core.odin.constants import DEFAULT_DATA_DIR, ENV_DATA_DIR
except Exception:  # pragma: no cover - optional; fallback
    DEFAULT_DATA_DIR = "tmp/odin"
    ENV_DATA_DIR = "ODIN_DATA_DIR"


def _current_month_key() -> str:
    # UTC year-month, e.g., "2025-08"
    import datetime as _dt
    now = _dt.datetime.now(_dt.UTC)
    return f"{now.year:04d}-{now.month:02d}"


def _parse_overrides(cfg: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for part in cfg.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        try:
            out[k] = int(v)
        except Exception:
            continue
    return out


class TenantQuotaMiddleware:
    """Enforce simple per-tenant monthly request quotas.

    Controls via env:
      - ODIN_TENANT_QUOTA_MONTHLY_REQUESTS: default monthly request cap per tenant (int)
      - ODIN_TENANT_QUOTA_OVERRIDES: comma-separated per-tenant overrides, e.g. "acme=5000,globex=20000"
      - ODIN_TENANT_HEADER: header name carrying tenant id (default X-ODIN-Tenant)

    Exempt paths: /health, /metrics, /docs, /openapi.json, /.well-known/odin/jwks
    Returns 429 rate limit style on quota exceeded: body "tenant_quota_exceeded".
    """

    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()
        # counts[(month_key, tenant)] = count
        self._counts: Dict[Tuple[str, str], int] = {}
        self._persist_on = os.getenv("ODIN_TENANT_QUOTA_PERSIST", "0").lower() in ("1", "true", "yes")

        # Load persisted counts for the current month if enabled
        if self._persist_on:
            try:
                mk = _current_month_key()
                persisted = self._persist_load(mk)
                if persisted:
                    with self._lock:
                        for t, v in persisted.items():
                            self._counts[(mk, t)] = int(v)
            except Exception:
                pass
        # expose a snapshot function for usage endpoints
        def _snapshot():
            with self._lock:
                # return a shallow copy grouped by tenant for current month
                mk = _current_month_key()
                out: Dict[str, int] = {}
                for (k_m, k_t), v in self._counts.items():
                    if k_m != mk:
                        continue
                    out[k_t] = out.get(k_t, 0) + v
                return {"month": mk, "tenants": out}

        # attach for discovery by routes
        try:
            # type: ignore[attr-defined]
            self.usage_snapshot = _snapshot  # pyright: ignore
        except Exception:
            pass

    def _data_dir(self) -> Path:
        return Path(os.getenv(ENV_DATA_DIR, DEFAULT_DATA_DIR))

    def _persist_path(self, month_key: str) -> Path:
        return self._data_dir() / "usage" / f"requests-{month_key}.json"

    def _persist_load(self, month_key: str) -> Dict[str, int]:
        p = self._persist_path(month_key)
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                tenants = data.get("tenants", {})
                out: Dict[str, int] = {}
                for k, v in tenants.items():
                    try:
                        out[str(k)] = int(v)
                    except Exception:
                        continue
                return out
        except Exception:
            return {}
        return {}

    def _persist_write_current(self):
        if not self._persist_on:
            return
        mk = _current_month_key()
        tenants: Dict[str, int] = {}
        with self._lock:
            for (k_m, k_t), v in self._counts.items():
                if k_m != mk:
                    continue
                tenants[k_t] = tenants.get(k_t, 0) + int(v)
        try:
            p = self._persist_path(mk)
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {"month": mk, "tenants": tenants}
            p.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        except Exception:
            # best-effort; ignore persistence failures
            pass

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)
        path = request.url.path
        # Skip known non-billable endpoints
        if path in ("/health", "/metrics", "/docs", "/openapi.json") or path.startswith("/.well-known/odin/"):
            return await self.app(scope, receive, send)

        # Read config once per request
        default_quota_env = os.getenv("ODIN_TENANT_QUOTA_MONTHLY_REQUESTS")
        try:
            default_quota = int(default_quota_env) if default_quota_env is not None else 0
        except Exception:
            default_quota = 0
        overrides = _parse_overrides(os.getenv("ODIN_TENANT_QUOTA_OVERRIDES", ""))

        # Determine tenant id (prefer request.state.tenant_id set by TenantMiddleware)
        try:
            tenant = getattr(request.state, "tenant_id", None)
        except Exception:
            tenant = None
        if not tenant:
            # Try headers as a fallback
            hdr = os.getenv("ODIN_TENANT_HEADER", "X-ODIN-Tenant")
            tenant = request.headers.get(hdr)

        # If no tenant, allow (upstream TenantMiddleware may enforce requirement)
        if not tenant:
            return await self.app(scope, receive, send)

        # Determine limit: per-tenant override first, else default if >0
        if tenant in overrides:
            limit = overrides[tenant]
        else:
            limit = default_quota
        # If neither override nor default provides a positive limit, do not enforce
        if limit <= 0:
            # Treat 0 or negative as unlimited for that tenant
            return await self.app(scope, receive, send)

        key = (_current_month_key(), str(tenant))
        # Fast path: increment and check under lock
        with self._lock:
            cur = self._counts.get(key, 0)
            if cur >= limit:
                # Already exceeded
                if _pol is not None:
                    try:
                        _pol.labels(rule="tenant_quota_exceeded", route=path).inc()
                    except Exception:
                        pass
                if _qblock is not None:
                    try:
                        _qblock.labels(tenant=str(tenant)).inc()
                    except Exception:
                        pass
                resp = Response(status_code=429, content=b"tenant_quota_exceeded", media_type="text/plain")
                return await resp(scope, receive, send)
            # Consume 1 unit
            self._counts[key] = cur + 1
            if _qcons is not None:
                try:
                    _qcons.labels(tenant=str(tenant)).inc()
                except Exception:
                    pass
        # best-effort persistence of snapshot
        self._persist_write_current()

        return await self.app(scope, receive, send)
