from __future__ import annotations

import json
import os
from typing import Optional, Dict, Any

from fastapi import HTTPException, Request

# Use the canonical HTTP signature helpers
from libs.odin_core.odin.http_sig import verify_v1
from apps.gateway.metrics import MET_HTTP_SIG_VERIFY


def _load_jwks_from_env() -> Optional[Dict[str, Any]]:
    """Load JWKS from an inline env var for local/testing scenarios.

    Env var: ODIN_HTTP_JWKS_INLINE — contains a JWKS JSON string.
    """
    jwks_inline = os.getenv("ODIN_HTTP_JWKS_INLINE")
    if jwks_inline:
        try:
            return json.loads(jwks_inline)
        except Exception:
            return None
    return None


async def require_http_signature(request: Request):
    """FastAPI dependency: verify X-ODIN-HTTP-Signature over the exact request body.

    Behavior controlled by env var ODIN_HTTP_SIGN_REQUIRE:
    - When set to "1", missing/invalid signatures raise 401.
    - Otherwise, verification is best-effort and result stored in request.state.odin_http.
    """
    require = os.getenv("ODIN_HTTP_SIGN_REQUIRE", "0") == "1"
    sig = request.headers.get("X-ODIN-HTTP-Signature")
    if not sig:
        if require:
            raise HTTPException(status_code=401, detail="odin.httpsig.missing")
        # annotate best-effort
        request.state.odin_http = {"ok": False, "reason": "missing"}
        try:
            MET_HTTP_SIG_VERIFY.labels(service="gateway", outcome="missing").inc()
        except Exception:
            pass
        return

    # Resolve JWKS: prefer header URL > env inline
    jwks = None
    jwks_hdr = request.headers.get("X-ODIN-JWKS")
    if jwks_hdr and jwks_hdr.startswith("http"):
        try:
            # local-only fetch; in tests we usually set env-inline to avoid network
            import httpx

            r = httpx.get(jwks_hdr, timeout=5.0)
            r.raise_for_status()
            jwks = r.json()
        except Exception:
            jwks = None

    if jwks is None:
        jwks = _load_jwks_from_env()
    if jwks is None:
        if require:
            raise HTTPException(status_code=401, detail="odin.httpsig.no_jwks")
        request.state.odin_http = {"ok": False, "reason": "no_jwks"}
        try:
            MET_HTTP_SIG_VERIFY.labels(service="gateway", outcome="no_jwks").inc()
        except Exception:
            pass
        return

    body = await request.body()
    # We verify against the path only (matches signer behavior)
    path = request.url.path
    try:
        info = verify_v1(method=request.method, path=path, body=body, header=sig, jwks=jwks)
        request.state.odin_http = info
        try:
            outcome = "pass" if getattr(info, "ok", False) else "fail"
            MET_HTTP_SIG_VERIFY.labels(service="gateway", outcome=outcome).inc()
        except Exception:
            pass
    except Exception as e:
        if require:
            raise HTTPException(status_code=401, detail=f"odin.httpsig.invalid:{e}")
        request.state.odin_http = {"ok": False, "reason": f"invalid:{e}"}
        try:
            MET_HTTP_SIG_VERIFY.labels(service="gateway", outcome="fail").inc()
        except Exception:
            pass
