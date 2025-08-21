from __future__ import annotations

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import orjson
from apps.gateway.metrics import (
    CONTENT_TYPE_LATEST,
    REG,
    REQS,
    LAT,
    generate_latest,
)
import time
from pathlib import Path
from libs.odin_core.odin.constants import ENV_DATA_DIR, DEFAULT_DATA_DIR
import os
import asyncio
from datetime import datetime

# Enhanced ODIN features
from libs.odin_core.odin.cache import get_cache, init_cache_managers, cache_health_check
from libs.odin_core.odin.connection_pool import get_pool_manager, connection_health_check
from libs.odin_core.odin.security import (
    get_certificate_pinner, get_audit_logger, get_rate_limiter,
    create_security_headers, log_security_event, SecurityEvent, SecurityLevel,
    security_health_check
)
from libs.odin_core.odin.tracing import trace_operation, get_tracer
from libs.odin_core.odin.migration_manager import MigrationManager

# OML core
from libs.odin_core.odin.oml import to_oml_c, compute_cid, get_default_sft
from libs.odin_core.odin.ope import OpeKeypair, sign_over_content
from libs.odin_core.odin.security.keystore import (
    load_keypair_from_env,
    load_keystore_from_json_env,
    ensure_keystore_file,
)
from libs.odin_core.odin.jsonutil import canonical_json_bytes
from libs.odin_core.odin.constants import WELL_KNOWN_ODIN_JWKS_PATH, ENV_JWKS_JSON, ENV_JWKS_PATH, ENV_SINGLE_PUBKEY, ENV_SINGLE_PUBKEY_KID, ENV_DATA_DIR, DEFAULT_DATA_DIR
from libs.odin_core.odin.jwks import KeyRegistry
from cryptography.hazmat.primitives import serialization
import json
import base64
from functools import lru_cache
from libs.odin_core.odin.middleware import ProofDiscoveryMiddleware
from apps.gateway.middleware.proof_enforcement import ProofEnforcementMiddleware
from apps.gateway.middleware.response_signing import ResponseSigningMiddleware
from apps.gateway.receipts import router as receipts_router
from apps.gateway.envelope import router as envelope_router
from apps.gateway.negotiation import router as negotiation_router
from apps.gateway.sft import router as sft_router
from apps.gateway.translate import router as translate_router
from apps.gateway.discovery import router as discovery_router
from apps.gateway.sft_maps import router as sft_maps_router
from libs.odin_core.odin.envelope import ProofEnvelope
from apps.gateway.ledger import router as ledger_router
from apps.gateway.bridge import router as bridge_router
from gateway.routers.bridge_pro import router as bridge_pro_router
from apps.gateway.receipts_transform import receipts_transform_router
from apps.gateway.receipts_index import router as receipts_index_router
from apps.gateway.services import services_router
from apps.gateway.registry import router as registry_router
from apps.gateway.runtime import wire_startup
from apps.gateway import admin as admin_router
from apps.gateway.admin_reload_router import admin_router as admin_dynamic_router, attach_reloader
from apps.gateway.relay_mesh import mesh_router
from apps.gateway.middleware.http_sign_enforcement import HttpSignEnforcementMiddleware
from apps.gateway.middleware.tenant import TenantMiddleware
from apps.gateway.middleware.quota import TenantQuotaMiddleware
# 0.9.0-beta features
from apps.gateway.middleware.vai import VAIMiddleware
from apps.gateway.admin_vai import vai_admin_router
from apps.gateway.streaming import stream_router
from billing.routes import router as billing_router
from billing.webhooks import router as stripe_webhook_router
from apps.gateway.pack_loader import realm_pack_loader
# BYOM Playground routers
from gateway.routers.byok import router as byok_router
from gateway.routers.demo import router as demo_router
# Research Engine router
from gateway.routers.research import router as research_router
try:
    from libs.odin_core.odin.hop_index import router as hop_index_router  # type: ignore
except Exception:
    hop_index_router = None  # type: ignore
from apps.gateway.metrics import policy_violations_total as MET_POLICY_VIOLATIONS
import logging

_log = logging.getLogger(__name__)

# --- Optional OpenTelemetry tracing (enabled via env: ODIN_OTEL!="0") ---
def _maybe_init_tracing() -> None:
    import os as _os
    if _os.getenv("ODIN_OTEL", "0") in ("0", "false", "False"):
        return
    try:
        from opentelemetry import trace as _trace  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
        # Prefer GCP exporter if requested and project is set; else OTLP
        exporter = None
        if _os.getenv("ODIN_OTEL_EXPORTER", "").lower() == "gcp" and _os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                from opentelemetry.exporter.gcp_trace import GCPSpanExporter  # type: ignore
                exporter = GCPSpanExporter()
            except Exception:
                exporter = None
        if exporter is None:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
                # Honor standard OTLP envs (OTEL_EXPORTER_OTLP_ENDPOINT, headers)
                exporter = OTLPSpanExporter()
            except Exception:
                exporter = None
        if exporter is None:
            return
        res = Resource.create({"service.name": "odin-gateway"})
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
        _log.info("OpenTelemetry tracing enabled")
    except Exception:
        # Tracing is optional; fail open
        pass


def _orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Initialize enhanced ODIN features
    try:
        # Initialize caching layer
        cache = await get_cache()
        cache_managers = await init_cache_managers()
        app.state.cache = cache
        app.state.cache_managers = cache_managers
        _log.info("✅ Cache layer initialized")
        
        # Initialize connection pools
        pool_manager = await get_pool_manager()
        app.state.pool_manager = pool_manager
        _log.info("✅ Connection pools initialized")
        
        # Initialize security systems
        cert_pinner = get_certificate_pinner()
        audit_logger = get_audit_logger()
        rate_limiter = get_rate_limiter()
        app.state.cert_pinner = cert_pinner
        app.state.audit_logger = audit_logger
        app.state.rate_limiter = rate_limiter
        _log.info("✅ Security systems initialized")
        
        # Initialize migration manager
        migration_manager = MigrationManager()
        app.state.migration_manager = migration_manager
        _log.info("✅ Migration manager initialized")
        
    except Exception as e:
        _log.error(f"Failed to initialize enhanced features: {e}")
    
    # Pre-warm HEL policy and SFT maps registries; start optional watchers
    try:
        wire_startup(app)
    except Exception:
        # Non-fatal in production if watchers or reload encounter errors
        pass

    # Load realm pack
    try:
        pack_uri = os.getenv("ODIN_REALM_PACK_URI")
        if pack_uri:
            realm_pack_loader.load_pack(pack_uri)
    except Exception as e:
        _log.error(f"Failed to load realm pack: {e}")
        
    # Attach dynamic reloader if available
    try:
        attach_reloader(app)
    except Exception:
        pass
    # Minimal main.py touch equivalent: set access logger level
    try:
        import logging as _logging
        _logging.getLogger("uvicorn.access").setLevel(_logging.INFO)
    except Exception:
        pass
    # Yield control to application runtime
    yield
    
    # Cleanup on shutdown
    try:
        if hasattr(app.state, 'cache') and app.state.cache:
            await app.state.cache.disconnect()
        if hasattr(app.state, 'pool_manager') and app.state.pool_manager:
            await app.state.pool_manager.close_all()
        _log.info("✅ Enhanced features cleaned up")
    except Exception as e:
        _log.error(f"Cleanup error: {e}")


app = FastAPI(
    title="ODIN Protocol Gateway", 
    version="1.0.0",
    description="""
# ODIN Protocol - The Enterprise AI Intranet

**Secure, verifiable, and compliant AI-to-AI communication platform**

## 🚀 Key Features

- **🔒 Zero-Trust Security**: Cryptographic proof chains, HTTP signatures
- **🏢 Multi-Tenant**: Complete isolation with quota management  
- **💰 Enterprise Ready**: Bridge Pro payment processing, Research Engine
- **📊 Full Observability**: Prometheus metrics, distributed tracing

## 🏗️ Core Services

### Bridge Pro Payment Processing
Enterprise-grade ISO 20022 payment transformation with approval workflows.

### Research Engine  
Multi-tenant AI experimentation platform with secure BYOM integration.

### SFT Translation
Semantic Format Transformation with advanced validation and linting.

## 📋 Authentication

Most endpoints require either:
- **HTTP Signatures**: For service-to-service communication
- **Admin Tokens**: For administrative operations  
- **BYOM Tokens**: For playground access (15-minute TTL)

## 🔗 Related Links

- [Documentation](https://odin-protocol.com/docs)
- [SDK Examples](https://github.com/Maverick0351a/ODINAIMESH/tree/main/packages/sdk)
- [Enterprise Sales](mailto:enterprise@odin-protocol.com)
    """,
    lifespan=_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "deepLinking": True,
        "displayRequestDuration": True,
        "docExpansion": "list",
        "operationsSorter": "method",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "tryItOutEnabled": True
    }
)
# Initialize optional tracing after app is created so FastAPIInstrumentor can hook
_maybe_init_tracing()

# Configure CORS for production deployment
import os
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

# Attach tenant middleware early so downstream sees tenant_id on request.state
app.add_middleware(TenantMiddleware)
# Enforce per-tenant monthly quotas if configured
app.add_middleware(TenantQuotaMiddleware)
# VAI (Verifiable Agent Identity) middleware for 0.9.0-beta
app.add_middleware(VAIMiddleware)
# Enable enforcement only when ODIN_ENFORCE_ROUTES is set to non-empty
if (os.getenv("ODIN_ENFORCE_ROUTES", "").strip()):
    app.add_middleware(ProofEnforcementMiddleware)
# Enable HTTP signature enforcement when ODIN_HTTP_SIGN_ENFORCE_ROUTES set
if (os.getenv("ODIN_HTTP_SIGN_ENFORCE_ROUTES", "").strip()):
    app.add_middleware(HttpSignEnforcementMiddleware)
# Enable response signing only when ODIN_SIGN_ROUTES is set to non-empty
if (os.getenv("ODIN_SIGN_ROUTES", "").strip()):
    app.add_middleware(ResponseSigningMiddleware)

# Enhanced HEL Middleware with RTN and Federation integration
try:
    from gateway.middleware.enhanced_hel import EnhancedHELMiddleware, build_hel_config
    
    hel_config = build_hel_config(
        realm=os.getenv("ODIN_REALM", "default"),
        rtn_enabled=os.getenv("ODIN_RTN_ENABLED", "true").lower() == "true",
        federation_enabled=os.getenv("ODIN_FEDERATION_ENABLED", "true").lower() == "true",
        default_unit_type=os.getenv("ODIN_DEFAULT_UNIT_TYPE", "compute_units")
    )
    
    app.add_middleware(EnhancedHELMiddleware, hel_config=hel_config)
except ImportError:
    pass

# Always add discovery last so it can observe and augment final headers
app.add_middleware(ProofDiscoveryMiddleware)
# Include the transform receipts router BEFORE the generic receipts router to avoid
# path conflicts where /v1/receipts/{cid} could swallow /v1/receipts/transform.
app.include_router(receipts_index_router)
app.include_router(receipts_router)
app.include_router(envelope_router)
app.include_router(negotiation_router)
app.include_router(sft_router)
app.include_router(translate_router)
app.include_router(discovery_router)
app.include_router(sft_maps_router)
app.include_router(ledger_router)
app.include_router(bridge_router)
app.include_router(bridge_pro_router)
app.include_router(services_router)
app.include_router(registry_router)
app.include_router(admin_router.router)
app.include_router(admin_dynamic_router)
app.include_router(mesh_router)
# 0.9.0-beta: VAI admin endpoints
app.include_router(vai_admin_router)
# 0.9.0-beta: Optional streaming endpoints
if os.getenv("ODIN_STREAMING_ENABLED", "0") != "0":
    app.include_router(stream_router)
# BYOM Playground endpoints
app.include_router(byok_router)
app.include_router(demo_router)
# Research Engine endpoints
app.include_router(research_router)
app.include_router(billing_router)
app.include_router(stripe_webhook_router)
if hop_index_router is not None:
    app.include_router(hop_index_router)

# Strategic Bet Endpoints
# 1. RTN (Receipts Transparency Network)
try:
    from apps.gateway.rtn import router as rtn_router
    app.include_router(rtn_router)
except ImportError:
    pass

# 2. Federation & Settlement
try:
    from apps.gateway.federation import router as federation_router
    app.include_router(federation_router)
except ImportError:
    pass

# 3. Payments Bridge Pro
try:
    from apps.gateway.payments import router as payments_router
    app.include_router(payments_router)
except ImportError:
    pass

# simple metrics are provided by apps.gateway.metrics (REG, REQS, LAT)


# Startup is handled via lifespan above


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    try:
        resp = await call_next(request)
        return resp
    finally:
        # Best-effort: include tenant label if present
        try:
            tenant = getattr(request.state, "tenant_id", None) or "-"
        except Exception:
            tenant = "-"
        LAT.labels(request.url.path, request.method).observe(time.perf_counter() - start)
        REQS.labels(request.url.path, request.method).inc()
        try:
            from apps.gateway.metrics import tenant_requests_total as _TRE, tenant_request_latency_seconds as _TLAT
            _TRE.labels(tenant=tenant, path=request.url.path, method=request.method).inc()
            _TLAT.labels(tenant=tenant, path=request.url.path, method=request.method).observe(time.perf_counter() - start)
        except Exception:
            pass


# --- Per-IP rate limiting (simple token-bucket) -----------------------------
_rl_state: dict[str, tuple[float, float]] = {}


def _ip_from_request(req: Request) -> str:
    # Prefer X-Forwarded-For when behind a proxy; fall back to client host
    try:
        xf = req.headers.get("x-forwarded-for") or req.headers.get("X-Forwarded-For")
        if xf:
            return xf.split(",")[0].strip()
    except Exception:
        pass
    try:
        return (req.client.host if req.client else "?")  # type: ignore[attr-defined]
    except Exception:
        return "?"


def _ip_rate_limited(ip: str) -> bool:
    # Env knobs: ODIN_GATEWAY_RATE_LIMIT_QPS (float per IP); 0 disables; <0 blocks all
    qps_env = os.getenv("ODIN_GATEWAY_RATE_LIMIT_QPS")
    if qps_env is None:
        return False
    try:
        qps = float(qps_env)
    except Exception:
        qps = 5.0
    if qps == 0:
        return False
    if qps < 0:
        return True
    import time as _t

    last_ts, tokens = _rl_state.get(ip, (0.0, qps))
    now = _t.perf_counter()
    if last_ts == 0.0:
        last_ts = now
        tokens = qps
    # Refill
    elapsed = now - last_ts
    tokens = min(qps, tokens + elapsed * qps)
    last_ts = now
    if tokens >= 1.0:
        tokens -= 1.0
        _rl_state[ip] = (last_ts, tokens)
        return False
    _rl_state[ip] = (last_ts, tokens)
    return True


@app.middleware("http")
async def per_ip_rate_limit_mw(request: Request, call_next):
    # Only enforce when env is set
    if os.getenv("ODIN_GATEWAY_RATE_LIMIT_QPS") is None:
        return await call_next(request)
    ip = _ip_from_request(request)
    limited = _ip_rate_limited(ip)
    if limited:
        try:
            MET_POLICY_VIOLATIONS.labels(rule="rate_limited", route=request.url.path).inc()
        except Exception:
            pass
        return Response(status_code=429, content=b"rate_limited", media_type="text/plain")
    return await call_next(request)


@app.get("/health")
def health():
    return {"ok": True, "service": "gateway"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(REG), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/echo")
async def echo(request: Request):
    """Lightweight echo endpoint: returns the raw JSON body or bytes.

    Accepts arbitrary JSON; useful for signature enforcement tests where shape is irrelevant.
    """
    try:
        body = await request.json()
    except Exception:
        # Fallback to raw text when not JSON
        body = (await request.body()).decode("utf-8", errors="ignore")
        return {"echo": body}

    # Preserve legacy contract: if a JSON object with a string `message` field is provided,
    # return that string under `echo`.
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return {"echo": body["message"]}

    # Otherwise echo back the parsed value as-is under `echo` (string/number/bool/null/object/array)
    return {"echo": body}


@app.get("/whoami")
def whoami(request: Request):
    try:
        tenant = getattr(request.state, "tenant_id", None)
    except Exception:
        tenant = None
    return {"ok": True, "tenant": tenant}


# ---- Minimal translate -> OML wiring ----
class TranslateIn(BaseModel):
    content: str
    source_lang: str | None = None
    target_lang: str = "en"


@lru_cache(maxsize=1)
def _get_signing_keypair() -> OpeKeypair:
    # Prefer persistent keystore under ODIN_KEYSTORE_PATH (or tmp/odin/keystore.json)
    ks_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(
        os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json"
    )
    try:
        ks, active = ensure_keystore_file(ks_path)
        if active and active in ks:
            return ks[active]
        # fallback to deterministic first
        if ks:
            return sorted(ks.items(), key=lambda kv: kv[0])[0][1]
    except Exception:
        pass
    # env-only fallback
    loaded = load_keypair_from_env()
    if loaded is not None:
        return loaded.keypair
    # JSON env fallback
    ks = load_keystore_from_json_env() or {}
    if ks:
        return sorted(ks.items(), key=lambda kv: kv[0])[0][1]
    # ephemeral last resort
    return OpeKeypair.generate("ephemeral")


# Note: /v1/translate is now provided by apps.gateway.translate router, which
# supports both back-compat shape and new mapping mode. The legacy inline
# handler has been removed to avoid path conflicts and validation issues.


# ---- Verify endpoint ----
class VerifyIn(BaseModel):
    ope: dict
    cid: str | None = None
    path: str | None = None
    bytes_b64: str | None = None


@app.post("/v1/verify")
def verify_endpoint(body: VerifyIn):
    from libs.odin_core.odin.ope import verify_over_content
    from base64 import b64decode

    # Load bytes from file or inline; prefer inline
    content: bytes | None = None
    if body.bytes_b64:
        try:
            content = b64decode(body.bytes_b64 + "==")
        except Exception:
            raise HTTPException(status_code=400, detail="invalid bytes_b64")
    elif body.path:
        p = Path(body.path)
        if not p.exists():
            raise HTTPException(status_code=400, detail="path not found")
        content = p.read_bytes()
    else:
        raise HTTPException(status_code=400, detail="missing content (path or bytes_b64)")

    expected = body.cid
    res = verify_over_content(body.ope, content, expected_oml_cid=expected)
    return res


# ---- SFT registry endpoints ----
@app.get("/v1/sft/default")
def get_sft_default():
    sft = get_default_sft()
    # Provide both JSON-hash and CBOR-CID for compatibility
    sft_json = canonical_json_bytes(sft)
    # compute CID over canonical CBOR of SFT map
    try:
        import cbor2  # local import to avoid unused if not hit

        sft_cbor = cbor2.dumps(sft, canonical=True)
        sft_cid = compute_cid(sft_cbor)
    except Exception:
        sft_cid = None
    from libs.odin_core.odin.crypto.blake3_hash import blake3_256_b64u

    return {
        "version": 1,
        "sft": sft,
        "json_hash_b3_256_b64u": blake3_256_b64u(sft_json),
        **({"cbor_cid": sft_cid} if sft_cid else {}),
    }


# Ledger endpoints are provided by apps.gateway.ledger router


# ---- JWKS publication ----
def _b64u(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@app.get(WELL_KNOWN_ODIN_JWKS_PATH)
def jwks_well_known():
    # First try env-driven registry (inline JWKS, JWKS path, or single pubkey)
    try:
        reg = KeyRegistry.from_env()
        env_jwks = reg.to_jwks()
        # If single key came from ENV_SINGLE_PUBKEY, expose active_kid for backward-compat with tests
        if os.getenv(ENV_SINGLE_PUBKEY):
            kid = (os.getenv(ENV_SINGLE_PUBKEY_KID) or "env").strip() or "env"
            return {**env_jwks, "active_kid": kid}
        # If inline/path provided, just return as-is
        if env_jwks["keys"]:
            return env_jwks
    except ValueError:
        raise HTTPException(status_code=500, detail="invalid_ODIN_OPE_JWKS")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"jwks_error:{type(e).__name__}")

    # Fallback: Build from persistent keystore
    ks_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(
        os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json"
    )
    try:
        ks, active = ensure_keystore_file(ks_path)
        keys = []
        for kid, kp in ks.items():
            raw = kp.public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            jwk = {"kty": "OKP", "crv": "Ed25519", "x": _b64u(raw), "kid": kid}
            keys.append(jwk)
        return {"keys": keys, "active_kid": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"jwks_error:{type(e).__name__}")


# ---- ODIN Core semantics (static, well-known) ----
WELL_KNOWN_ODIN_CORE_SEMANTICS_PATH = "/.well-known/odin/semantics/core@v0.1.json"


@app.get(WELL_KNOWN_ODIN_CORE_SEMANTICS_PATH)
def odin_core_semantics_v0_1():
    return {
        "id": "core@v0.1",
        "description": "ODIN Core Semantics v0.1 — minimal shared vocabulary for AI-to-AI intents.",
        "fields": {
            "intent": {"type": "string", "required": True},
            "actor": {"type": ["string", "object"], "required": False},
            "subject": {"type": ["string", "object"], "required": False},
            "resource": {"type": ["string", "object"], "required": False},
            "action": {"type": "string", "required": False},
            "amount": {"type": "number", "required": False},
            "units": {"type": "string", "required": False},
            "reason": {"type": "string", "required": False},
            "ts": {"type": ["integer", "string"], "required": False},
        },
        "intents": {
            "echo": {},
            "translate": {},
            "transfer": {},
            "notify": {},
            "query": {},
        },
    }


# Discovery endpoint moved to apps.gateway.discovery router


# Enhanced health checks for monitoring
@app.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check including all enhanced systems."""
    async with trace_operation("health_check", {"type": "detailed"}):
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {}
        }
        
        overall_healthy = True
        
        # Cache health
        try:
            cache_health = await cache_health_check()
            health_status["components"]["cache"] = cache_health
            if cache_health["status"] not in ["healthy", "degraded"]:
                overall_healthy = False
        except Exception as e:
            health_status["components"]["cache"] = {"status": "error", "message": str(e)}
            overall_healthy = False
            
        # Connection pool health
        try:
            conn_health = await connection_health_check()
            health_status["components"]["connections"] = conn_health
            if conn_health["status"] not in ["healthy", "degraded"]:
                overall_healthy = False
        except Exception as e:
            health_status["components"]["connections"] = {"status": "error", "message": str(e)}
            overall_healthy = False
            
        # Security systems health
        try:
            security_health = await security_health_check()
            health_status["components"]["security"] = security_health
            if security_health["status"] not in ["healthy", "degraded"]:
                overall_healthy = False
        except Exception as e:
            health_status["components"]["security"] = {"status": "error", "message": str(e)}
            overall_healthy = False
            
        # Migration system health
        try:
            if hasattr(app.state, 'migration_manager'):
                migration_status = await app.state.migration_manager.get_migration_status()
                health_status["components"]["migrations"] = {
                    "status": "healthy",
                    "current_version": migration_status.get("current_version"),
                    "pending_migrations": len(migration_status.get("pending_migrations", []))
                }
        except Exception as e:
            health_status["components"]["migrations"] = {"status": "error", "message": str(e)}
            
        # Set overall status
        if not overall_healthy:
            health_status["status"] = "degraded"
            
        return health_status


@app.get("/metrics/security")
async def security_metrics():
    """Get security metrics for monitoring."""
    async with trace_operation("security_metrics"):
        try:
            audit_logger = get_audit_logger()
            rate_limiter = get_rate_limiter()
            cert_pinner = get_certificate_pinner()
            
            return {
                "security_events": audit_logger.get_security_metrics(),
                "rate_limiting": rate_limiter.get_rate_limit_stats(),
                "certificate_pinning": cert_pinner.get_violation_stats(),
                "timestamp": time.time()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Metrics error: {e}")


@app.get("/metrics/performance")
async def performance_metrics():
    """Get performance metrics."""
    async with trace_operation("performance_metrics"):
        try:
            performance_data = {
                "timestamp": time.time(),
                "request_metrics": {
                    "total_requests": REG.get_sample_value("odin_gateway_requests_total") or 0,
                    "request_latency_avg": REG.get_sample_value("odin_gateway_request_duration_seconds_sum") / max(REG.get_sample_value("odin_gateway_request_duration_seconds_count") or 1, 1)
                }
            }
            
            # Add cache stats if available
            if hasattr(app.state, 'cache_managers'):
                cache_health = await cache_health_check()
                performance_data["cache"] = cache_health.get("stats", {})
                
            # Add connection pool stats
            if hasattr(app.state, 'pool_manager'):
                conn_health = await connection_health_check()
                performance_data["connections"] = conn_health.get("stats", {})
                
            return performance_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Performance metrics error: {e}")


# Enhanced middleware for security and monitoring
@app.middleware("http")
async def enhanced_security_middleware(request: Request, call_next):
    """Enhanced security middleware with rate limiting and audit logging."""
    start_time = time.time()
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    
    # Rate limiting
    try:
        rate_limiter = get_rate_limiter()
        
        # Determine rate limit rule based on endpoint
        rule_type = "default"
        if request.url.path.startswith("/bridge-pro"):
            rule_type = "bridge_pro"
        elif request.url.path.startswith("/research"):
            rule_type = "research"
        elif request.headers.get("authorization"):
            rule_type = "api_key"
            
        if not rate_limiter.is_allowed(client_ip, rule_type):
            # Log rate limit violation
            await log_security_event(SecurityEvent(
                event_type="rate_limit_exceeded",
                severity=SecurityLevel.MEDIUM,
                timestamp=datetime.utcnow(),
                source_ip=client_ip,
                user_agent=user_agent,
                details={"rule_type": rule_type, "path": request.url.path},
                action_taken="request_blocked"
            ))
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
    except HTTPException:
        raise
    except Exception as e:
        _log.error(f"Rate limiting error: {e}")
        
    # Process request
    response = await call_next(request)
    
    # Add security headers
    security_headers = create_security_headers()
    for header, value in security_headers.items():
        response.headers[header] = value
        
    # Log suspicious activity
    if response.status_code >= 400:
        await log_security_event(SecurityEvent(
            event_type="http_error",
            severity=SecurityLevel.LOW if response.status_code < 500 else SecurityLevel.MEDIUM,
            timestamp=datetime.utcnow(),
            source_ip=client_ip,
            user_agent=user_agent,
            details={
                "status_code": response.status_code,
                "path": request.url.path,
                "method": request.method
            }
        ))
        
    # Update metrics
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

