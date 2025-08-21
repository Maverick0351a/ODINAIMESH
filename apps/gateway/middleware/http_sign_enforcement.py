import json, os
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from libs.odin_core.odin.http_sig import verify_v1  # uses Ed25519, ts_ns, method, path, body


def _load_inline_jwks() -> Optional[dict]:
    raw = os.getenv("ODIN_HTTP_JWKS_INLINE", "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _routes_from_env() -> list[str]:
    raw = os.getenv("ODIN_HTTP_SIGN_ENFORCE_ROUTES", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _match(path: str, prefixes: list[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


class HttpSignEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Enforces ODIN HTTP-signature on selected route prefixes.

        Env:
      - ODIN_HTTP_SIGN_ENFORCE_ROUTES: comma-separated prefixes (/v1/relay,/v1/bridge)
      - ODIN_HTTP_SIGN_REQUIRE: "1" (default) -> 401 on missing/invalid, "0" -> annotate only
      - ODIN_HTTP_JWKS_INLINE: JWKS JSON for verification (required unless you add another resolver)
            - ODIN_HTTP_SIGN_SKEW_SEC or ODIN_HTTP_SIGN_SKEW: allowed clock skew in seconds (default 120)
    """

    def __init__(self, app):
        super().__init__(app)
        self.require = os.getenv("ODIN_HTTP_SIGN_REQUIRE", "1") != "0"
        self.prefixes = _routes_from_env()
        skew_env = os.getenv("ODIN_HTTP_SIGN_SKEW_SEC") or os.getenv("ODIN_HTTP_SIGN_SKEW") or "120"
        try:
            self.skew = int(skew_env)
        except Exception:
            self.skew = 120
        self.jwks_inline = _load_inline_jwks()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # If not enabled or path doesn't match, pass-through
        if not self.prefixes or not _match(request.url.path, self.prefixes):
            return await call_next(request)

        # Read and buffer body (needed for signature check, then re-inject)
        body = await request.body()

        hdr = request.headers.get("X-ODIN-HTTP-Signature")
        if not hdr:
            if self.require:
                return JSONResponse(
                    {"detail": {"error": "odin.http_sig.missing", "message": "HTTP signature required"}},
                    status_code=401,
                )
            # soft mode
            request = Request(request.scope, receive=_make_receive(body))
            return await call_next(request)

        jwks = self.jwks_inline
        try:
            # Verify signature over METHOD + PATH + BODY with ts_ns skew check
            v = verify_v1(
                method=request.method,
                path=request.url.path,  # path only (no query) to match signer’s contract
                body=body,
                header=hdr,
                jwks=jwks,  # type: ignore[arg-type]
            )
            ok = bool(v.get("ok"))
        except Exception as e:
            ok = False
            v = {"error": str(e)}

        if not ok:
            if self.require:
                return JSONResponse(
                    {
                        "detail": {
                            "error": "odin.http_sig.invalid",
                            "message": "HTTP signature invalid",
                            "verify": v,
                        }
                    },
                    status_code=401,
                )
            # soft mode -> annotate request state and continue
            request.state.http_sig = {"ok": False, "verify": v}
            request = Request(request.scope, receive=_make_receive(body))
            return await call_next(request)

        # Attach verification context for downstream
        request.state.http_sig = {"ok": True, "kid": v.get("kid"), "ts_ns": v.get("ts_ns")}
        request = Request(request.scope, receive=_make_receive(body))
        return await call_next(request)


def _make_receive(body: bytes):
    async def _receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return _receive
