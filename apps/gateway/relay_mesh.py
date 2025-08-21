from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response

from libs.odin_core.odin.router_id import get_router_id, new_trace_id, append_forwarded_by, hop_number
from libs.odin_core.odin import apply_redactions  # optional redaction for stored receipts
from libs.odin_core.odin.storage import create_storage_from_env, receipt_metadata_from_env
from apps.gateway.metrics import mesh_hops_total
from .security.id_token import maybe_get_id_token  # optional GCP ID token helper
try:
    from libs.odin_core.odin.hop_index import HopReceipt, record_hop  # type: ignore
except Exception:  # pragma: no cover
    HopReceipt, record_hop = None, None  # type: ignore


mesh_router = APIRouter()


def _get_trace_id(req: Request, body: Optional[Dict[str, Any]]) -> str:
    tid = req.headers.get("X-ODIN-Trace-Id")
    if isinstance(body, dict) and not tid:
        tid = str(body.get("trace_id") or "").strip() or None
    return tid or new_trace_id()


def _json_dumps(obj: Any) -> bytes:
    try:
        import orjson as _oj  # type: ignore

        return _oj.dumps(obj)
    except Exception:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@mesh_router.post("/v1/mesh/forward")
async def mesh_forward(request: Request) -> Response:
    """
    Minimal mesh forwarder:
    - Assign or continue a trace (X-ODIN-Trace-Id)
    - Append this router to X-ODIN-Forwarded-By
    - Persist a hop receipt under receipts/hops/<trace_id>-<hop_no>.json
    - Optionally forward to body.next_url with the body.payload

    Request body (unwrapped):
    {
      "payload": obj,            # forwarded POST body if next_url provided
      "next_url": "http://...", # optional; if absent, no outbound call
      "trace_id": "..."          # optional; else header or generated
    }
    """
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    router = get_router_id()
    incoming_fwd = request.headers.get("X-ODIN-Forwarded-By")
    fwd = append_forwarded_by(incoming_fwd, router)
    trace_id = _get_trace_id(request, body)
    hop_no = hop_number(fwd)
    hop_id = f"{trace_id}-{hop_no}"

    # Build and persist a hop receipt
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
    except Exception:
        tenant_id = None
    receipt = {
        "type": "odin.mesh.hop",
        "trace_id": trace_id,
        "hop_no": hop_no,
        "hop_id": hop_id,
        "router_id": router,
        "forwarded_by": fwd,
        "ts_ms": int(time.time() * 1000),
        **({"tenant": tenant_id} if tenant_id else {}),
        "request": {
            "method": request.method,
            "path": request.url.path,
        },
    }
    storage = create_storage_from_env()
    key = f"receipts/hops/{hop_id}.json"
    try:
        # Include optional TTL metadata; attach tenant in metadata when available
        meta = receipt_metadata_from_env() or {}
        if tenant_id:
            meta = {**meta, "odin_tenant": str(tenant_id)} if meta else {"odin_tenant": str(tenant_id)}
        storage.put_bytes(key, _json_dumps(receipt), content_type="application/json", metadata=meta or None)
    except Exception:
        # Non-fatal; continue and increment write-failure metric
        try:
            from apps.gateway.metrics import receipt_write_failures_total as _rcpt_fail
            _rcpt_fail.labels(kind=os.getenv("ODIN_STORAGE_BACKEND", "local").lower()).inc()
        except Exception:
            pass
    try:
        mesh_hops_total.labels(route="mesh.forward").inc()
    except Exception:
        pass

    # Optional forward
    next_url = None
    payload = None
    if isinstance(body, dict):
        # Accept both 'next_url' and legacy/test alias 'target_url'
        next_url = body.get("target_url") or body.get("next_url")
        payload = body.get("payload")

    # Default response body if no forwarding occurs
    body_out: Any = {"ok": True, "trace_id": trace_id, "hop_id": hop_id}

    if isinstance(next_url, str) and next_url:
        try:
            import httpx  # local import; optional dependency
        except Exception:
            raise HTTPException(status_code=500, detail="missing_dependency:httpx")

        headers = {
            "X-ODIN-Trace-Id": trace_id,
            "X-ODIN-Forwarded-By": fwd,
            "Content-Type": "application/json",
        }
        # Propagate tenant header if present
        try:
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                hdr = os.getenv("ODIN_TENANT_HEADER", "X-ODIN-Tenant")
                headers[hdr] = str(tenant_id)
        except Exception:
            pass
        # Propagate W3C trace headers when present (for cross-hop tracing)
        try:
            tp = request.headers.get("traceparent")
            ts = request.headers.get("tracestate")
            if tp:
                headers["traceparent"] = tp
            if ts:
                headers["tracestate"] = ts
        except Exception:
            pass
        # Optional Google Cloud ID token for Cloud Run → Cloud Run calls
        try:
            if os.getenv("ODIN_MESH_ID_TOKEN", "1") != "0":
                aud_override = os.getenv("ODIN_ID_TOKEN_AUDIENCE") or os.getenv("ODIN_GCP_ID_TOKEN_AUDIENCE")
                token = await maybe_get_id_token(next_url, aud_override)
                if token:
                    headers.setdefault("Authorization", f"Bearer {token}")
        except Exception:
            # Non-fatal; proceed without Authorization if token acquisition fails
            pass

        # Resilience knobs
        retries = int(os.getenv("ODIN_MESH_RETRIES", "2") or 2)
        backoff_ms = int(os.getenv("ODIN_MESH_RETRY_BACKOFF_MS", "200") or 200)

        # Execute with simple bounded retries on network errors and 5xx
        last_exc: Optional[Exception] = None
        attempt = 0
        while attempt <= retries:
            try:
                # Avoid passing constructor args so tests can monkeypatch AsyncClient with a minimal stub
                async with httpx.AsyncClient() as client:
                    r = await client.post(next_url, json=payload, headers=headers)
                status = getattr(r, "status_code", None)
                if isinstance(status, int) and status >= 500:
                    raise RuntimeError(f"upstream_5xx:{status}")
                if isinstance(status, int) and status >= 400:
                    detail = {
                        "error": "mesh.next_error",
                        "status": status,
                        "body": getattr(r, "text", None),
                    }
                    raise HTTPException(status_code=502, detail=detail)
                ct = (getattr(r, "headers", {}) or {}).get("content-type", "")
                if isinstance(ct, str) and "application/json" in ct:
                    body_out = r.json()
                else:
                    raw_text = getattr(r, "text", None)
                    body_out = {"raw": raw_text} if raw_text is not None else {}
                last_exc = None
                break
            except HTTPException:
                raise
            except Exception as e:
                last_exc = e
                attempt += 1
                if attempt <= retries:
                    try:
                        await _async_sleep(backoff_ms)
                    except Exception:
                        time.sleep(backoff_ms / 1000.0)
        if last_exc is not None:
            raise HTTPException(status_code=502, detail={"error": f"mesh.request_failed:{type(last_exc).__name__}", "message": str(last_exc)})

    # Persist a richer hop receipt including outbound result snapshot
    try:
        # Apply optional redactions only to the stored receipt (not HTTP response)
        _pat_env = os.getenv("ODIN_REDACT_FIELDS")
        _patterns_raw = [p.strip() for p in (_pat_env.split(",") if _pat_env else []) if p.strip()]

        def _norm(patterns, ctx):
            # ctx: 'in' or 'out' — strip common prefixes when applying to a subtree
            outp = []
            for p in patterns:
                segs = p.split(".")
                if ctx == "in" and segs and segs[0] in ("payload", "in", "request", "body"):
                    segs = segs[1:]
                elif ctx == "out" and segs and segs[0] in ("out", "response", "result"):
                    segs = segs[1:]
                np = ".".join([s for s in segs if s])
                if np:
                    outp.append(np)
            return outp

        _p_in = _norm(_patterns_raw, "in")
        _p_out = _norm(_patterns_raw, "out")

        safe_in = apply_redactions(payload, _p_in) if isinstance(payload, (dict, list)) and _p_in else payload
        safe_out = apply_redactions(body_out, _p_out) if isinstance(body_out, (dict, list)) and _p_out else body_out

        # Optional simple DLP masking for stored receipts (emails, SSNs, cc-like numbers)
        try:
            if os.getenv("ODIN_DLP_SIMPLE", "0") not in ("0", "false", "False"):
                from libs.odin_core.odin.dlp import apply_simple_dlp  # type: ignore
                if isinstance(safe_in, (dict, list)):
                    safe_in = apply_simple_dlp(safe_in)
                if isinstance(safe_out, (dict, list)):
                    safe_out = apply_simple_dlp(safe_out)
        except Exception:
            pass

        receipt_full = {
            "type": "odin.mesh.hop",
            "trace_id": trace_id,
            "hop": hop_no,
            "hop_id": hop_id,
            "from": router,
            "forwarded_by": fwd,
            "to_url": next_url,
            "in": safe_in,
            "out": safe_out,
            "ts_ms": int(time.time() * 1000),
            **({"tenant": tenant_id} if tenant_id else {}),
        }
        meta2 = receipt_metadata_from_env() or {}
        if tenant_id:
            meta2 = {**meta2, "odin_tenant": str(tenant_id)} if meta2 else {"odin_tenant": str(tenant_id)}
        storage.put_bytes(key, _json_dumps(receipt_full), content_type="application/json", metadata=meta2 or None)
        # Also record into hop index for fast chain queries (best-effort)
        try:
            if HopReceipt and record_hop:
                # Extract CIDs if present in payload/out; else placeholders
                in_cid = str((payload or {}).get("oml_cid") or (payload or {}).get("cid") or "")
                out_cid = str((body_out or {}).get("oml_cid") or (body_out or {}).get("cid") or "")
                signer_id = os.getenv("ODIN_SIGNER_KID") or None
                hr = HopReceipt(
                    trace_id=trace_id,
                    hop=hop_no,
                    in_cid=in_cid,
                    out_cid=out_cid,
                    signer=signer_id,
                    meta={
                        "hop_id": hop_id,
                        "router": router,
                        "route": "mesh/forward",
                        "next": next_url,
                    },
                )
                record_hop(hr)  # type: ignore[misc]
        except Exception:
            pass
    except Exception:
        pass

    return Response(
        content=_json_dumps(body_out),
        media_type="application/json",
        headers={
            "X-ODIN-Trace-Id": trace_id,
            "X-ODIN-Forwarded-By": fwd,
            "X-ODIN-Hop-Id": hop_id,
            "X-ODIN-Receipt-Chain": f"{trace_id}:{hop_no}",
            # Try to expose a direct URL if the backend can generate it; else API path
            "X-ODIN-Hop-Receipt-URL": (
                storage.url_for(key) or f"/v1/receipts/hops/{hop_id}"
            ),
        },
    )


# lightweight awaitable sleep helper (avoids importing asyncio at module import for cold start)
async def _async_sleep(backoff_ms: int) -> None:
    try:
        import asyncio

        await asyncio.sleep(backoff_ms / 1000.0)
    except Exception:
        time.sleep(backoff_ms / 1000.0)
