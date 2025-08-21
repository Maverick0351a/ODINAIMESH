from __future__ import annotations

import json
import os
from typing import Optional, Dict, Any

from fastapi import HTTPException, Request

# Reuse core verifier
from libs.odin_core.odin.http_sig import verify_v1
from .metrics import MET_HTTP_SIG_VERIFY


def _load_jwks_from_env() -> Optional[Dict[str, Any]]:
    """
    Resolve JWKS from environment in this order:
    1) ODIN_HTTP_JWKS_INLINE (JSON string)
    2) ODIN_HTTP_JWKS_URL (HTTP(S) URL to fetch)
    """
    jwks_inline = os.getenv("ODIN_HTTP_JWKS_INLINE")
    if jwks_inline:
        try:
            return json.loads(jwks_inline)
        except Exception:
            return None
    jwks_url = os.getenv("ODIN_HTTP_JWKS_URL")
    if jwks_url and jwks_url.startswith("http"):
        try:
            import httpx
            r = httpx.get(jwks_url, timeout=5.0)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None
    return None


async def require_http_signature(request: Request):
    require = os.getenv("ODIN_HTTP_SIGN_REQUIRE", "0") == "1"
    sig = request.headers.get("X-ODIN-HTTP-Signature")
    if not sig:
        # Record metric regardless of require mode
        try:
            MET_HTTP_SIG_VERIFY.labels(service="agent_beta", outcome="missing").inc()
        except Exception:
            pass
        if require:
            raise HTTPException(status_code=401, detail="odin.httpsig.missing")
        request.state.odin_http = {"ok": False, "reason": "missing"}
        return

    jwks = None
    jwks_hdr = request.headers.get("X-ODIN-JWKS")
    if jwks_hdr and jwks_hdr.startswith("http"):
        try:
            import httpx
            r = httpx.get(jwks_hdr, timeout=5.0)
            r.raise_for_status()
            jwks = r.json()
        except Exception:
            jwks = None

    if jwks is None:
        jwks = _load_jwks_from_env()
    if jwks is None:
        # Record metric regardless of require mode
        try:
            MET_HTTP_SIG_VERIFY.labels(service="agent_beta", outcome="no_jwks").inc()
        except Exception:
            pass
        if require:
            raise HTTPException(status_code=401, detail="odin.httpsig.no_jwks")
        request.state.odin_http = {"ok": False, "reason": "no_jwks"}
        return

    body = await request.body()
    path = request.url.path
    try:
        info = verify_v1(method=request.method, path=path, body=body, header=sig, jwks=jwks)
        request.state.odin_http = info
        # Record success/fail metric based on dict value
        try:
            outcome = "pass" if (isinstance(info, dict) and info.get("ok", False)) else "fail"
            MET_HTTP_SIG_VERIFY.labels(service="agent_beta", outcome=outcome).inc()
        except Exception:
            pass
    except Exception as e:
        # Record failure regardless of require mode
        try:
            MET_HTTP_SIG_VERIFY.labels(service="agent_beta", outcome="fail").inc()
        except Exception:
            pass
        if require:
            raise HTTPException(status_code=401, detail=f"odin.httpsig.invalid:{e}")
        request.state.odin_http = {"ok": False, "reason": f"invalid:{e}"}
