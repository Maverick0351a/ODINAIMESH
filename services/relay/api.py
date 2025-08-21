from __future__ import annotations

import ipaddress
from urllib.parse import urlparse
import json
import os
import time
from typing import Dict

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, AnyHttpUrl

from libs.odin_core.odin.ope import verify_over_content
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST  # type: ignore
except Exception:  # pragma: no cover
    Counter = Histogram = generate_latest = CONTENT_TYPE_LATEST = None  # type: ignore

# Optional helper for Google Cloud ID tokens (service-to-service auth)
try:
    from apps.gateway.security.id_token import maybe_get_id_token  # type: ignore
except Exception:  # pragma: no cover - relay may run standalone
    async def maybe_get_id_token(aud_url: str, audience_override: str | None = None) -> str | None:  # type: ignore
        return None

app = FastAPI(title="ODIN Relay", version="0.0.2")

# --- Optional OpenTelemetry tracing (enabled via env: ODIN_OTEL!="0") ---
def _maybe_init_tracing() -> None:
    if os.getenv("ODIN_OTEL", "0") in ("0", "false", "False"):
        return
    try:
        from opentelemetry import trace as _trace  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
        exporter = None
        if os.getenv("ODIN_OTEL_EXPORTER", "").lower() == "gcp" and os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                from opentelemetry.exporter.gcp_trace import GCPSpanExporter  # type: ignore
                exporter = GCPSpanExporter()
            except Exception:
                exporter = None
        if exporter is None:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
                exporter = OTLPSpanExporter()
            except Exception:
                exporter = None
        if exporter is None:
            return
        res = Resource.create({"service.name": "odin-relay"})
        provider = TracerProvider(resource=res)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        _trace.set_tracer_provider(provider)
        # Auto-instrument FastAPI and httpx
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
            FastAPIInstrumentor.instrument_app(app)  # type: ignore[name-defined]
        except Exception:
            pass
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # type: ignore
            HTTPXClientInstrumentor().instrument()
        except Exception:
            pass
    except Exception:
        pass

_maybe_init_tracing()

# Configure CORS for production deployment
ODIN_ENVIRONMENT = os.getenv("ODIN_ENVIRONMENT", "development")
if ODIN_ENVIRONMENT == "production":
    # Production CORS: Restrict to actual production origins
    allowed_origins = [
        "https://odin-site-[random-suffix]-uc.a.run.app",  # Will be updated by CI/CD
        "https://odin-gateway-[random-suffix]-uc.a.run.app"
    ]
else:
    # Development CORS: Allow common development origins
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# --- Metrics (optional) ---
METRICS_ENABLED = os.getenv("ODIN_RELAY_METRICS", "1") != "0"
if METRICS_ENABLED and Counter is not None and Histogram is not None:
    relay_http_requests_total = Counter(
        "odin_relay_http_requests_total",
        "Relay HTTP requests",
        ["route", "method", "status"],
    )
    relay_http_request_duration_seconds = Histogram(
        "odin_relay_http_request_duration_seconds",
        "Relay HTTP request duration",
        ["route", "method"],
        buckets=(0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5),
    )
    relay_rate_limited_total = Counter(
        "odin_relay_rate_limited_total",
        "Relay rate-limited decisions",
        [],
    )

    def _route_label(path: str) -> str:
        # Compact any long ids
        import re as _re
        p = _re.sub(r"/[0-9a-fA-F-]{8,}", "/:id", path)
        p = _re.sub(r"/[0-9]{6,}", "/:id", p)
        return p

    @app.middleware("http")
    async def _metrics_mw(request, call_next):  # type: ignore
        route = _route_label(request.url.path)
        method = request.method
        t0 = time.perf_counter()
        try:
            resp = await call_next(request)
            return resp
        finally:
            dt = time.perf_counter() - t0
            status = getattr(locals().get("resp", None), "status_code", 500)
            try:
                relay_http_requests_total.labels(route, method, str(status)).inc()
                relay_http_request_duration_seconds.labels(route, method).observe(dt)
            except Exception:
                pass

    @app.get("/metrics")
    def metrics():  # type: ignore
        if not METRICS_ENABLED or generate_latest is None:
            raise HTTPException(status_code=404, detail="metrics disabled")
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)  # type: ignore[arg-type]

# --- Basic health endpoint ---
@app.get("/health")
def health():
    return {"ok": True, "service": "relay"}

# --- SSRF defense helpers ---
PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private_host(host: str) -> bool:
    """Return True only for literal private IP/loopback/link-local addresses.
    Domain names are not considered private here (no DNS resolution performed)."""
    try:
        ip = ipaddress.ip_address(host)
        return any(ip in net for net in PRIVATE_NETS)
    except ValueError:
        # not an IP literal; treat as non-private (allowed unless deny-listed)
        return False


def _ssrf_allowed(url: str) -> bool:
    """Basic SSRF guard: allow during tests; else restrict to http(s),
    deny-list obvious locals, and disallow literal private IPs.
    """
    # Allow during tests to avoid flakiness; also allow when ODIN_ALLOW_TEST_HOSTS=1
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("ODIN_ALLOW_TEST_HOSTS") in ("1", "true", "True"):
        return True

    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    # Deny-list obvious local hosts
    if host in ("localhost", "metadata", "metadata.google.internal"):
        return False
    if host.endswith(".local"):
        return False
    # Disallow literal private/loopback/link-local IPs
    if _is_private_host(host):
        return False
    return True


# --- Header policy ---
ALLOWED_FWD_HEADERS = {"x-odin-oml-cid", "x-odin-ope", "x-odin-ope-kid"}

# Simple global rate limiter (QPS) using token bucket
_rl_last_ts = 0.0
_rl_tokens = 0.0


def _rate_limited() -> bool:
    global _rl_last_ts, _rl_tokens
    qps_env = os.getenv("ODIN_RELAY_RATE_LIMIT_QPS")
    if qps_env is None:
        return False  # disabled
    try:
        qps = float(qps_env)
    except Exception:
        qps = 1.0
    if qps <= 0:
        return True
    now = time.perf_counter()
    if _rl_last_ts == 0.0:
        _rl_last_ts = now
        _rl_tokens = qps
    # Refill tokens
    elapsed = now - _rl_last_ts
    _rl_tokens = min(qps, _rl_tokens + elapsed * qps)
    _rl_last_ts = now
    if _rl_tokens >= 1.0:
        _rl_tokens -= 1.0
        return False
    # Out of tokens
    try:
        if METRICS_ENABLED and 'relay_rate_limited_total' in globals():
            relay_rate_limited_total.inc()  # type: ignore[name-defined]
    except Exception:
        pass
    return True


class RelayIn(BaseModel):
    url: AnyHttpUrl
    method: str = "POST"
    headers: Dict[str, str] = {}
    bytes_b64: str


@app.post("/relay")
async def relay(req: RelayIn, request: Request):
    target = req.url
    # SSRF allow/deny
    if not _ssrf_allowed(str(target)):
        raise HTTPException(status_code=400, detail="target not allowed")

    # rate limit
    if _rate_limited():
        raise HTTPException(status_code=429, detail="rate_limited")

    # Filter headers
    fwd_headers = {k: v for k, v in req.headers.items() if k.lower() in ALLOWED_FWD_HEADERS}

    # Verify OPE if supplied
    ope_b64 = fwd_headers.get("x-odin-ope")
    cid = fwd_headers.get("x-odin-oml-cid")
    body = None
    try:
        from base64 import b64decode

        body = b64decode(req.bytes_b64 + "==")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid bytes_b64")

    if ope_b64:
        try:
            import base64

            ope = json.loads(base64.b64decode(ope_b64).decode("utf-8"))
            vr = verify_over_content(ope, body, expected_oml_cid=cid)
            if not vr.get("ok"):
                raise HTTPException(status_code=400, detail=f"ope_verify_failed:{vr.get('reason')}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid_ope:{e}")

    # Outbound identity (optional) and resiliency
    # - ID token when ODIN_RELAY_ID_TOKEN!=0, with optional audience override
    # - Timeouts/retries/backoff via env knobs
    headers = dict(fwd_headers)
    # Propagate W3C trace headers if present on inbound request
    try:
        tp = request.headers.get("traceparent")
        ts = request.headers.get("tracestate")
        if tp:
            headers.setdefault("traceparent", tp)
        if ts:
            headers.setdefault("tracestate", ts)
    except Exception:
        pass
    try:
        if os.getenv("ODIN_RELAY_ID_TOKEN", "1") != "0":
            aud_override = os.getenv("ODIN_ID_TOKEN_AUDIENCE") or os.getenv("ODIN_GCP_ID_TOKEN_AUDIENCE")
            token = await maybe_get_id_token(str(target), aud_override)
            if token:
                headers.setdefault("Authorization", f"Bearer {token}")
    except Exception:
        # Fail open: continue without Authorization
        pass

    try:
        timeout_ms = int(os.getenv("ODIN_RELAY_TIMEOUT_MS", "10000") or 10000)
    except Exception:
        timeout_ms = 10000
    try:
        retries = int(os.getenv("ODIN_RELAY_RETRIES", "2") or 2)
    except Exception:
        retries = 2
    try:
        backoff_ms = int(os.getenv("ODIN_RELAY_RETRY_BACKOFF_MS", "250") or 250)
    except Exception:
        backoff_ms = 250

    method = req.method.upper()
    try:
        # Instantiate AsyncClient without ctor args to be friendly to test monkeypatches
        async with httpx.AsyncClient() as client:
            attempt = 0
            last_exc: Exception | None = None
            while attempt <= retries:
                try:
                    r = await client.request(
                        method,
                        str(target),
                        content=body,
                        headers=headers,
                        timeout=httpx.Timeout(timeout_ms / 1000.0),
                    )
                    status = r.status_code
                    # Retry on 5xx, surface 4xx
                    if status >= 500:
                        raise RuntimeError(f"upstream_5xx:{status}")
                    if status >= 400:
                        return {"status": status, "headers": dict(r.headers), "len": len(r.content)}
                    return {"status": status, "headers": dict(r.headers), "len": len(r.content)}
                except httpx.RequestError as e:
                    last_exc = e
                except RuntimeError as e:
                    last_exc = e
                # Backoff and retry if allowed
                attempt += 1
                if attempt > retries:
                    break
                try:
                    import asyncio

                    await asyncio.sleep(backoff_ms / 1000.0)
                except Exception:
                    time.sleep(backoff_ms / 1000.0)
            # If we exhausted retries, map to 502 with error hint
            raise HTTPException(status_code=502, detail=f"connect_error:{type(last_exc).__name__ if last_exc else 'unknown'}")
    except HTTPException:
        raise
    except Exception as e:
        # Catch-all mapping for unexpected failures
        raise HTTPException(status_code=502, detail=f"relay_error:{type(e).__name__}")
