from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

# Use the core verifier we ship in libs/odin_core
from libs.odin_core.odin.verifier import verify as verify_core
from libs.odin_core.odin.hel_policy import evaluate_policy
from apps.gateway.runtime import get_hel_policy
import logging
from apps.gateway.metrics import policy_violations_total as MET_POLICY_VIOLATIONS
# 0.9.0-beta: OpenTelemetry integration for security events
from libs.odin_core.odin.telemetry_bridge import emit_security_telemetry
# 0.9.0-beta: SIEM/SOAR integration
from libs.odin_core.odin.siem_integration import emit_policy_violation_alert

logger = logging.getLogger(__name__)


# Constants
HDR_WWW_AUTH = "WWW-Authenticate"

# Env config
ENV_ENFORCE_ROUTES = "ODIN_ENFORCE_ROUTES"        # comma-separated prefixes, e.g. "/v1/relay,/v1/secured"
ENV_POLICY_PATH = "ODIN_HEL_POLICY_PATH"          # JSON policy file (optional)
ENV_REQUIRE_ENVELOPE = "ODIN_ENFORCE_REQUIRE"     # "1" to require proof strictly (default 1)

# Error codes
ERR_MISSING_PROOF = "odin.proof.missing"
ERR_INVALID_PROOF = "odin.proof.invalid"
ERR_POLICY_BLOCKED = "odin.policy.blocked"
ERR_JWKS_FORBIDDEN_HOST = "odin.policy.jwks_host_forbidden"
ERR_BAD_REQUEST = "odin.request.invalid_json"
ERR_CONTENT_POLICY = "odin.policy.content_blocked"  # kept for compatibility; not used directly below


@dataclass
class HelPolicy:
    allow_kids: List[str]
    deny_kids: List[str]
    allowed_jwks_hosts: List[str]

    @classmethod
    def from_file(cls, path: Optional[str]) -> "HelPolicy":
        if not path or not os.path.isfile(path):
            return cls(allow_kids=["*"], deny_kids=[], allowed_jwks_hosts=["localhost", "127.0.0.1"])
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            allow_kids=list(data.get("allow_kids", ["*"])),
            deny_kids=list(data.get("deny_kids", [])),
            allowed_jwks_hosts=list(data.get("allowed_jwks_hosts", ["localhost", "127.0.0.1"])),
        )

    def kid_allowed(self, kid: str) -> bool:
        if any(fnmatch.fnmatch(kid, pat) for pat in self.deny_kids):
            return False
        return any(fnmatch.fnmatch(kid, pat) for pat in self.allow_kids)

    def host_allowed(self, host: str) -> bool:
        host = (host or "").lower()
        return any(fnmatch.fnmatch(host, pat.lower()) for pat in self.allowed_jwks_hosts)


class ProofEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Requires a valid ODIN ProofEnvelope on selected routes before the request
    reaches your handlers. On failure returns 401/403 with structured JSON.

    Input JSON shape:
      { "payload": <any>, "proof": { oml_cid, kid, ope, jwks_inline?, jwks_url?, oml_c_b64 } }

    Configuration envs:
      - ODIN_ENFORCE_ROUTES      comma-separated path prefixes (e.g. "/v1/relay,/v1/secured")
      - ODIN_HEL_POLICY_PATH     optional JSON file: {allow_kids, deny_kids, allowed_jwks_hosts}
      - ODIN_ENFORCE_REQUIRE     "1" strict (default), "0" soft attach only
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        prefixes = os.getenv(ENV_ENFORCE_ROUTES, "").strip()
        self.prefixes: List[str] = [p.strip() for p in prefixes.split(",") if p.strip()]
        self.strict: bool = os.getenv(ENV_REQUIRE_ENVELOPE, "1") not in ("0", "false", "False")
        policy_path = os.getenv(ENV_POLICY_PATH)
        self.policy = HelPolicy.from_file(policy_path)
        # Keep the full JSON policy for content evaluation
        self.policy_content = {}
        if policy_path and os.path.isfile(policy_path):
            try:
                with open(policy_path, "r", encoding="utf-8") as f:
                    self.policy_content = json.load(f) or {}
            except Exception:
                self.policy_content = {}

    async def dispatch(self, request: Request, call_next):
        # Only enforce for configured prefixes + JSON methods
        if not self._should_enforce(request):
            return await call_next(request)

        # Buffer the body so we can read & then restore for downstream
        try:
            raw = await request.body()
        except Exception:
            return self._err(status.HTTP_400_BAD_REQUEST, ERR_BAD_REQUEST, "unable to read request body")
        self._restore_body(request, raw)

        # Parse JSON
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return self._err(status.HTTP_400_BAD_REQUEST, ERR_BAD_REQUEST, "body must be JSON {payload, proof}")

        proof = data.get("proof") or data.get("envelope")
        if not isinstance(proof, dict):
            if self.strict:
                try:
                    MET_POLICY_VIOLATIONS.labels(rule=ERR_MISSING_PROOF, route=request.url.path).inc()
                except Exception as e:
                    logger.debug("policy metric inc failed: %s", e)
                return self._err(
                    status.HTTP_401_UNAUTHORIZED,
                    ERR_MISSING_PROOF,
                    "proof envelope is required",
                    {"hint": "wrap your payload as {'payload': <...>, 'proof': {...}}"},
                )
            else:
                try:
                    MET_POLICY_VIOLATIONS.labels(rule=ERR_MISSING_PROOF, route=request.url.path).inc()
                except Exception as e:
                    logger.debug("policy metric inc failed: %s", e)
            # Non-strict mode: just attach context and continue
            request.state.odin = {"ok": False, "reason": "no proof"}
            # If user sent a wrapper {payload, proof?}, unwrap payload for downstream
            if isinstance(data, dict) and "payload" in data:
                try:
                    new_raw = json.dumps(data["payload"], separators=(",", ":")).encode("utf-8")
                    self._restore_body(request, new_raw)
                except Exception:
                    # fall back to original body
                    self._restore_body(request, raw)
            return await call_next(request)

        # Resolve JWKS and host (for policy)
        jwks_source, jwks_host = self._resolve_jwks_source(request, proof)

        # Verify using core verifier (envelope flow)
        try:
            res = verify_core(envelope=proof, jwks=jwks_source)
        except Exception as e:  # defensive
            try:
                MET_POLICY_VIOLATIONS.labels(rule=ERR_INVALID_PROOF, route=request.url.path).inc()
            except Exception as e:
                logger.debug("policy metric inc failed: %s", e)
            return self._err(
                status.HTTP_401_UNAUTHORIZED,
                ERR_INVALID_PROOF,
                f"verifier_error:{type(e).__name__}:{e}",
            )

        if not res.ok:
            if self.strict:
                try:
                    MET_POLICY_VIOLATIONS.labels(rule=ERR_INVALID_PROOF, route=request.url.path).inc()
                except Exception as e:
                    logger.debug("policy metric inc failed: %s", e)
                return self._err(
                    status.HTTP_401_UNAUTHORIZED,
                    ERR_INVALID_PROOF,
                    res.reason or "proof invalid",
                )
            else:
                try:
                    MET_POLICY_VIOLATIONS.labels(rule=ERR_INVALID_PROOF, route=request.url.path).inc()
                except Exception as e:
                    logger.debug("policy metric inc failed: %s", e)
            request.state.odin = {"ok": False, "reason": res.reason or "invalid"}
            return await call_next(request)

        # Policy checks
        kid = (res.kid or proof.get("kid") or "").strip()
        if not self.policy.kid_allowed(kid):
            try:
                MET_POLICY_VIOLATIONS.labels(rule=ERR_POLICY_BLOCKED, route=request.url.path).inc()
                
                # 0.9.0-beta: Emit security telemetry for policy violations
                violation = {
                    "rule": ERR_POLICY_BLOCKED,
                    "message": "kid blocked by policy",
                    "kid": kid
                }
                request_context = {
                    "tenant_id": getattr(request.state, "tenant_id", "unknown"),
                    "route": request.url.path,
                    "path": request.url.path,
                    "method": request.method
                }
                emit_security_telemetry(violation, request_context)
            except Exception as e:
                logger.debug("policy metric inc failed: %s", e)
            return self._err(
                status.HTTP_403_FORBIDDEN,
                ERR_POLICY_BLOCKED,
                "kid blocked by policy",
                {"kid": kid},
            )
        if jwks_host and not self.policy.host_allowed(jwks_host):
            try:
                MET_POLICY_VIOLATIONS.labels(rule=ERR_JWKS_FORBIDDEN_HOST, route=request.url.path).inc()
            except Exception as e:
                logger.debug("policy metric inc failed: %s", e)
            return self._err(
                status.HTTP_403_FORBIDDEN,
                ERR_JWKS_FORBIDDEN_HOST,
                f"jwks host '{jwks_host}' not allowed",
                {"host": jwks_host},
            )

        # Content policy checks (payload-level HEL rules)
        if isinstance(data, dict):
            # Determine normalized payload for content checks: unwrap if wrapper used
            normalized_payload = data.get("payload") if "payload" in data else data
            # If the first-level payload is itself a wrapper (e.g., translate request), unwrap once more
            if (
                isinstance(normalized_payload, dict)
                and "payload" in normalized_payload
                and "intent" not in normalized_payload
                and isinstance(normalized_payload.get("payload"), dict)
            ):
                normalized_payload = normalized_payload["payload"]
            # Fetch cached HEL policy (env/file is read once and cached by runtime)
            policy_dict = get_hel_policy()
            pol_eval = evaluate_policy(
                normalized_payload if isinstance(normalized_payload, dict) else {},
                policy_dict or {},
            )
            if pol_eval and not pol_eval.allowed:
                # For content policy failures, return a unified error code and a flat 'details' list
                violations_list = [vi.as_dict() for vi in pol_eval.violations]
                route = request.url.path
                # Increment per-violation using the violation code when available
                try:
                    for v in violations_list:
                        MET_POLICY_VIOLATIONS.labels(rule=v.get("code", "unknown"), route=route).inc()
                        
                        # 0.9.0-beta: Emit security telemetry for HEL policy violations
                        violation = {
                            "rule": v.get("code", "unknown"),
                            "message": v.get("message", "HEL policy violation"),
                            "policy_details": v
                        }
                        request_context = {
                            "tenant_id": getattr(request.state, "tenant_id", "unknown"),
                            "route": route,
                            "path": route,
                            "method": request.method,
                            "client_ip": request.client.host if hasattr(request, "client") else None
                        }
                        emit_security_telemetry(violation, request_context)
                        
                        # 0.9.0-beta: Emit SIEM/SOAR alert for high-severity violations
                        try:
                            await emit_policy_violation_alert(violation, request_context)
                        except Exception as siem_error:
                            logger.debug(f"SIEM alert failed: {siem_error}")
                except Exception as e:
                    logger.debug("policy metric inc failed: %s", e)
                # Structured log for logs-based metrics and alerting
                try:
                    logger.warning(
                        "odin.policy.blocked",
                        extra={
                            "error": ERR_POLICY_BLOCKED,
                            "route": route,
                            "kid": kid,
                            "violations": violations_list,
                        },
                    )
                except Exception:
                    pass
                return JSONResponse(
                    {
                        "error": ERR_POLICY_BLOCKED,
                        "message": "payload violates content policy",
                        "details": violations_list,
                    },
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        # Attach context and proceed
        request.state.odin = {"ok": True, "kid": kid, "cid": res.cid}
        # If client used wrapper {payload, proof}, unwrap payload for downstream handlers
        if isinstance(data, dict) and "payload" in data:
            try:
                new_raw = json.dumps(data["payload"], separators=(",", ":")).encode("utf-8")
                self._restore_body(request, new_raw)
            except Exception:
                # if any issue, keep original body
                self._restore_body(request, raw)
        else:
            self._restore_body(request, raw)  # restore original
        return await call_next(request)

    def _should_enforce(self, request: Request) -> bool:
        if not self.prefixes:
            return False
        path = request.url.path or ""
        if request.method not in ("POST", "PUT", "PATCH"):
            return False
        return any(path.startswith(p) for p in self.prefixes)

    def _restore_body(self, request: Request, raw: bytes) -> None:
        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}

        # Starlette hack: restore internal receive for downstream
        request._receive = receive  # type: ignore[attr-defined]

    def _resolve_jwks_source(self, request: Request, proof: Dict) -> Tuple[Optional[str | Dict], Optional[str]]:
        """Return jwks source (dict or absolute URL) and hostname for policy checks.
        We don't fetch here; the core verifier will fetch if given an URL.
        """
        jwks_inline = proof.get("jwks_inline")
        if isinstance(jwks_inline, dict) and jwks_inline.get("keys"):
            return jwks_inline, None
        jwks_url = proof.get("jwks_url")
        if isinstance(jwks_url, str) and jwks_url:
            url = jwks_url
            if url.startswith("/"):
                base = f"{request.url.scheme}://{request.url.netloc}"
                url = urljoin(base + "/", url.lstrip("/"))
            host = urlparse(url).hostname
            return url, host
        return None, None

    def _err(self, code: int, error: str, message: str, detail: Optional[Dict] = None) -> JSONResponse:
        headers = {}
        if code in (status.HTTP_401_UNAUTHORIZED,):
            headers[HDR_WWW_AUTH] = 'ODIN-Proof realm="odin", error="required"'
        body = {"error": error, "message": message}
        if detail:
            body["detail"] = detail
        return JSONResponse(body, status_code=code, headers=headers)
