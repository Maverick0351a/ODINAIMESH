from __future__ import annotations

import os
from typing import Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# Prefer the libs path; fall back to shim if available
try:  # pragma: no cover - import resolution
    from libs.odin_core.odin.sft import CORE_ID  # type: ignore
except Exception:  # pragma: no cover
    from odin_core.odin.sft import CORE_ID  # type: ignore


router = APIRouter()


def _abs_url(req: Request, path: str) -> str:
    """
    Build an absolute URL for `path` using the current request base.
    """
    base = str(req.base_url).rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _route_exists(req: Request, prefix: str) -> bool:
    try:
        for r in req.app.routes:  # type: ignore[attr-defined]
            if getattr(r, "path", "").startswith(prefix):
                return True
    except Exception:
        pass
    return False


def _parse_csv(val: str | None) -> List[str]:
    return [p.strip() for p in (val or "").split(",") if p.strip()]


def _http_sign_info() -> Dict[str, object]:
    prefixes = _parse_csv(os.getenv("ODIN_HTTP_SIGN_ENFORCE_ROUTES", ""))
    require = os.getenv("ODIN_HTTP_SIGN_REQUIRE", "1") != "0"
    try:
        skew = int(os.getenv("ODIN_HTTP_SIGN_SKEW_SEC", "120"))
    except Exception:
        skew = 120
    has_inline = bool(os.getenv("ODIN_HTTP_JWKS_INLINE", "").strip())
    return {
        "header": "X-ODIN-HTTP-Signature",
        "enforce_routes": prefixes,
        "require": require,
        "skew_sec": skew,
        "jwks_inline": has_inline,
    }


@router.get("/.well-known/odin/discovery.json")
async def odin_discovery(req: Request) -> JSONResponse:
    # Read env at request-time so tests can toggle without app restart
    enforce_routes = _parse_csv(os.getenv("ODIN_ENFORCE_ROUTES"))
    sign_routes = _parse_csv(os.getenv("ODIN_SIGN_ROUTES"))
    sign_embed = os.getenv("ODIN_SIGN_EMBED", "0") in ("1", "true", "True")
    transform_receipts_enabled = os.getenv("ODIN_TRANSFORM_RECEIPTS", "1") not in ("0", "false", "False")

    # Capabilities present if the route exists in this app
    caps: Dict[str, bool] = {
        "echo": _route_exists(req, "/v1/echo"),
        "translate": _route_exists(req, "/v1/translate"),
        "envelope": _route_exists(req, "/v1/envelope"),
        "verify": _route_exists(req, "/v1/verify"),
        "receipts": _route_exists(req, "/v1/receipts"),
        "sft": _route_exists(req, "/v1/sft"),
        "ledger": _route_exists(req, "/v1/ledger"),
        "relay": _route_exists(req, "/v1/relay"),
        "bridge": _route_exists(req, "/v1/bridge"),
        "bridge_openai": _route_exists(req, "/v1/bridge/openai"),
        # Expose the transform capability when transform receipts route is present
        "transform": _route_exists(req, "/v1/receipts/transform"),
    }
    # HTTP signing capability (advertised when code support exists)
    caps["http_signing"] = True

    # Proof negotiation and headers (kept in sync with middleware constants)
    try:
        from apps.gateway.middleware.response_signing import (  # type: ignore
            HDR_ACCEPT_PROOF,
            HDR_PROOF_STATUS,
            X_OML_CID,
            X_OML_C_PATH,
            X_OPE,
            X_OPE_KID,
        )
    except Exception:
        HDR_ACCEPT_PROOF = "X-ODIN-Accept-Proof"  # type: ignore
        HDR_PROOF_STATUS = "X-ODIN-Proof-Status"  # type: ignore
        X_OML_CID = "X-ODIN-OML-CID"  # type: ignore
        X_OML_C_PATH = "X-ODIN-OML-C-Path"  # type: ignore
        X_OPE = "X-ODIN-OPE"  # type: ignore
        X_OPE_KID = "X-ODIN-OPE-KID"  # type: ignore

    # Optional dynamic reload status
    dyn_status = None
    try:
        from apps.gateway.dynamic_runtime import dynamic_status  # type: ignore

        dyn_status = dynamic_status()
    except Exception:
        dyn_status = None

    doc = {
        "name": getattr(req.app, "title", "ODIN Gateway"),  # type: ignore[attr-defined]
        "service": "gateway",
        "version": os.getenv("ODIN_VERSION", "0.1.0"),
        "protocol": {"odin": "0.1", "proof_version": "1"},
        "jwks_url": _abs_url(req, "/.well-known/odin/jwks.json"),
        "negotiation": {
            "http_signing": {
                "request_header": "X-ODIN-HTTP-Signature",
                "jwks_header": "X-ODIN-JWKS",
            }
        },
        "proof": {
            "negotiate": {
                "request_header": HDR_ACCEPT_PROOF,
                "response_header": HDR_PROOF_STATUS,
                "modes": ["embed", "headers"],
            },
            "headers": [X_OML_CID, X_OML_C_PATH, X_OPE, X_OPE_KID],
            "discovery_headers": ["X-ODIN-JWKS", "X-ODIN-Proof-Version"],
        },
        "sft": {
            "core_id": CORE_ID,
            "core_url": "/v1/sft/core",
            "default_url": "/v1/sft/default",
        },
        "policy": {
            "enforce_routes": enforce_routes,
            "sign_routes": sign_routes,
            "sign_embed": sign_embed,
            "transform_receipts": transform_receipts_enabled,
        },
        "endpoints": {
            "echo": "/v1/echo",
            "translate": "/v1/translate",
            "bridge": "/v1/bridge",
            "bridge_openai": "/v1/bridge/openai",
            "envelope": "/v1/envelope",
            "verify": "/v1/verify",
            "receipts": "/v1/receipts/{cid}",
            "transform_receipt": "/v1/receipts/transform/{out_cid}",
            "receipts_transform_list": "/v1/receipts/transform",
            "mesh_forward": "/v1/mesh/forward",
            "receipts_hop_get": "/v1/receipts/hops/{id}",
            "receipts_hops_list": "/v1/receipts/hops",
            "receipts_chain_get": "/v1/receipts/chain/{trace_id}",
            "receipts_hops_chain_get": "/v1/receipts/hops/chain/{trace_id}",
            "ledger": "/v1/ledger",
            "sft_core": "/v1/sft/core",
            "sft_default": "/v1/sft/default",
            "sft_maps_list": "/v1/sft/maps",
            "sft_map_get": "/v1/sft/maps/{name}",
        "services_register": "/v1/services/register",
        "services_list": "/v1/services",
        "service_get": "/v1/services/{id}",
            "registry_register": "/v1/registry/register",
            "registry_list": "/v1/registry/services",
            "registry_get": "/v1/registry/services/{id}",
            "jwks": "/.well-known/odin/jwks.json",
            "discovery": "/.well-known/odin/discovery.json",
            "metrics": "/metrics",
            "health": "/health",
        },
    "capabilities": {**caps, "maps": True, "transform_index": True, "services": True, "registry": True, "mesh": True, "receipt_chain": True},
    "http_sign": _http_sign_info(),
    }

    # Attach live etags if dynamic reload is enabled
    if isinstance(dyn_status, dict):
        try:
            doc["dynamic"] = {
                "enabled": True,
                "policy_etag": (dyn_status.get("policy") or {}).get("etag"),
                "sft_registry_etag": (dyn_status.get("sft_registry") or {}).get("etag"),
                "ttl_secs": dyn_status.get("ttl_secs"),
            }
        except Exception:
            pass

    # 1.3 Discovery augmentation: reflect dynamic reloader state directly
    try:
        reloader = getattr(req.app.state, "reloader", None)  # type: ignore[attr-defined]
        if reloader is not None:
            # Top-level flags and etags, mirroring the provided snippet
            doc["policy_dynamic"] = True
            doc["sft_dynamic"] = True
            # Access underlying asset etags if present
            policy_etag = getattr(getattr(reloader, "policy", None), "etag", None)
            sft_etag = getattr(getattr(reloader, "sft_registry", None), "etag", None)
            if policy_etag is not None:
                doc["policy_etag"] = policy_etag
            if sft_etag is not None:
                doc["sft_registry_etag"] = sft_etag
    except Exception:
        pass

    # Advertise admin-driven dynamic policy/SFT reload if enabled
    admin_enabled = os.getenv("ODIN_ENABLE_ADMIN", "0") in ("1", "true", "True")
    try:
        doc["capabilities"]["policy_dynamic"] = admin_enabled
        doc["capabilities"]["sft_dynamic"] = admin_enabled
        if admin_enabled:
            doc["endpoints"]["admin_reload_policy"] = "/v1/admin/reload/policy"
            doc["endpoints"]["admin_reload_maps"] = "/v1/admin/reload/maps"
            # Optional dynamic reload endpoints
            doc["endpoints"]["admin_dynamic_status"] = "/v1/admin/dynamic/status"
            doc["endpoints"]["admin_dynamic_reload"] = "/v1/admin/dynamic/reload/{target}"
            # Also advertise consolidated reload/status admin (new router)
            doc["endpoints"]["admin_reload"] = "/v1/admin/reload"
            doc["endpoints"]["admin_reload_status"] = "/v1/admin/reload/status"
            # Optional compact admin capability signal
            doc["admin"] = {"reload": True}
    except Exception:
        pass

    # Small cache TTL; this is safe and helps avoid hot-loop clients
    headers = {"Cache-Control": "public, max-age=60"}
    return JSONResponse(doc, headers=headers)
