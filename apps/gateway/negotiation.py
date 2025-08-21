from __future__ import annotations

import os
from typing import Dict, Any, List
from fastapi import APIRouter, Request

# Reuse constants from middlewares to avoid drift
from apps.gateway.middleware.response_signing import (
    ENV_SIGN_ROUTES,
    ENV_SIGN_REQUIRE,
    ENV_SIGN_EMBED,
    WELL_KNOWN_JWKS,
    HDR_ACCEPT_PROOF,
    HDR_PROOF_STATUS,
)
from apps.gateway.middleware.proof_enforcement import (
    ENV_ENFORCE_ROUTES,
    ENV_REQUIRE_ENVELOPE,
    ENV_POLICY_PATH,
)

router = APIRouter()


def _csv_env(name: str) -> List[str]:
    raw = (os.getenv(name, "") or "").strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


def _bool_env(name: str, default: str = "1") -> bool:
    return os.getenv(name, default) not in ("0", "false", "False")


@router.get("/v1/negotiation")
def negotiation_introspection(request: Request) -> Dict[str, Any]:
    # Signing config
    sign_routes = _csv_env(ENV_SIGN_ROUTES)
    sign_require = _bool_env(ENV_SIGN_REQUIRE, "1")
    sign_embed = _bool_env(ENV_SIGN_EMBED, "1")

    # Enforcement config
    enforce_routes = _csv_env(ENV_ENFORCE_ROUTES)
    enforce_require = _bool_env(ENV_REQUIRE_ENVELOPE, "1")

    # Absolute URLs for JWKS, receipts, and core semantics
    base = f"{request.url.scheme}://{request.url.netloc}"
    jwks_url = f"{base}{WELL_KNOWN_JWKS}"
    receipt_template = f"{base}/v1/receipts/{{cid}}"
    semantics_core = f"{base}/.well-known/odin/semantics/core@v0.1.json"

    # Policy path echo
    policy_path = os.getenv(ENV_POLICY_PATH, "")

    return {
        "ok": True,
        "sign": {
            "routes": sign_routes,
            "require": sign_require,
            "embed": sign_embed,
        },
        "enforce": {
            "routes": enforce_routes,
            "require": enforce_require,
        },
        "headers": {
            "accept": HDR_ACCEPT_PROOF,
            "status": HDR_PROOF_STATUS,
        },
        "endpoints": {
            "jwks_url": jwks_url,
            "receipt_template": receipt_template,
            "semantics_core": semantics_core,
        },
        "exemptions": [
            "/metrics",
        ],
        "policy": {
            "path": policy_path,
        },
    }
