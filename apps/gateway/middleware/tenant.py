from __future__ import annotations

import os
import time
from typing import Callable

from fastapi import Request, Response

# Simple per-tenant token bucket state: tenant -> (last_ts, tokens)
_TENANT_BUCKETS: dict[str, tuple[float, float]] = {}


def _get_tenant_header_name() -> str:
    # Allow override; default to X-ODIN-Tenant; also support X-Tenant-Id as alt
    return os.getenv("ODIN_TENANT_HEADER", "X-ODIN-Tenant")


def extract_tenant_id(request: Request) -> str | None:
    """Extract tenant id from headers using configured header name.

    Falls back to common alternates when the primary header is missing.
    """
    try:
        name = _get_tenant_header_name()
        val = request.headers.get(name)
        if val:
            return val.strip() or None
        # Common alternates
        for alt in ("X-Tenant-Id", "X-Tenant", "X-ODIN-Tenant-Id"):
            v = request.headers.get(alt)
            if v:
                return v.strip() or None
    except Exception:
        pass
    return None


def _rate_limit_allowed(tenant: str) -> bool:
    # Env knobs: ODIN_TENANT_RATE_LIMIT_QPS
    qps_env = os.getenv("ODIN_TENANT_RATE_LIMIT_QPS")
    if qps_env is None:
        return True  # disabled
    try:
        qps = float(qps_env)
    except Exception:
        qps = 10.0
    if qps == 0:
        return True
    if qps < 0:
        return False
    last_ts, tokens = _TENANT_BUCKETS.get(tenant, (0.0, qps))
    now = time.perf_counter()
    if last_ts == 0.0:
        last_ts, tokens = now, qps
    # refill
    tokens = min(qps, tokens + (now - last_ts) * qps)
    last_ts = now
    if tokens >= 1.0:
        tokens -= 1.0
        _TENANT_BUCKETS[tenant] = (last_ts, tokens)
        return True
    _TENANT_BUCKETS[tenant] = (last_ts, tokens)
    return False


class TenantMiddleware:
    """Attach tenant id to request.state and enforce optional allow-list and rate limit.

    Env vars:
      - ODIN_TENANT_HEADER: header name to read (default: X-ODIN-Tenant)
      - ODIN_TENANT_REQUIRED: if set to a truthy value, require tenant header
      - ODIN_TENANT_ALLOWED: comma-separated list of allowed tenant ids
      - ODIN_TENANT_RATE_LIMIT_QPS: per-tenant QPS token bucket (float); 0 disables; <0 blocks all
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        request = Request(scope, receive=receive)

        # Extract and attach early so downstream middlewares/handlers can use it
        tenant = extract_tenant_id(request)
        request.state.tenant_id = tenant

        # Optional enforcement
        required = os.getenv("ODIN_TENANT_REQUIRED", "0").lower() in ("1", "true", "yes")
        allowed_cfg = os.getenv("ODIN_TENANT_ALLOWED", "")
        allowed = [t.strip() for t in allowed_cfg.split(",") if t.strip()] if allowed_cfg else None

        # Paths that should not be blocked even if required (health/metrics/docs)
        path = request.url.path
        if path in ("/health", "/metrics") or path.startswith("/.well-known") or path.startswith("/docs"):
            # proceed without enforcement but keep tenant on state
            return await self.app(scope, receive, send)

        # Require tenant if configured
        if required and not tenant:
            return await self._send_plain(send, 400, b"missing_tenant")

        # Allow-list
        if allowed is not None and tenant and tenant not in allowed:
            return await self._send_plain(send, 403, b"tenant_forbidden")

        # Per-tenant rate limit
        if tenant and not _rate_limit_allowed(tenant):
            try:
                # best-effort metric if available
                from apps.gateway.metrics import policy_violations_total as _pol
                _pol.labels(rule="tenant_rate_limited", route=path).inc()
            except Exception:
                pass
            return await self._send_plain(send, 429, b"tenant_rate_limited")

        # Continue
        return await self.app(scope, receive, send)

    async def _send_plain(self, send: Callable, status: int, body: bytes):
        headers = [(b"content-type", b"text/plain; charset=utf-8")]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
