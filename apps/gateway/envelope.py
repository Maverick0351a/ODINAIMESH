from __future__ import annotations

from fastapi import APIRouter, Request, Response
import os
import json
import base64
from typing import Any, Dict

from libs.odin_core.odin.oml import to_oml_c, compute_cid, get_default_sft
from libs.odin_core.odin.ope import OpeKeypair, sign_over_content
from libs.odin_core.odin.security.keystore import (
    load_keypair_from_env,
    load_keystore_from_json_env,
    ensure_keystore_file,
)
from libs.odin_core.odin.constants import WELL_KNOWN_ODIN_JWKS_PATH
from libs.odin_core.odin.jwks import KeyRegistry
from cryptography.hazmat.primitives import serialization
from libs.odin_core.odin.envelope import ProofEnvelope
# 0.9.0-beta: SBOM support
from libs.odin_core.odin.sbom import extract_sbom_from_request, enhance_receipt_with_sbom, record_sbom_metrics
# 0.9.0-beta: OpenTelemetry integration
from libs.odin_core.odin.telemetry_bridge import emit_receipt_telemetry, TraceContext
# 0.9.0-beta: Per-hop metering and billing
from libs.odin_core.odin.metering import create_operation_billing, enhance_receipt_with_marketplace_billing, auto_report_stripe_usage


router = APIRouter()


def _get_signing_keypair() -> OpeKeypair:
    ks_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(
        os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json"
    )
    try:
        ks, active = ensure_keystore_file(ks_path)
        if active and active in ks:
            return ks[active]
        if ks:
            return sorted(ks.items(), key=lambda kv: kv[0])[0][1]
    except Exception:
        pass
    loaded = load_keypair_from_env()
    if loaded is not None:
        return loaded.keypair
    ks = load_keystore_from_json_env() or {}
    if ks:
        return sorted(ks.items(), key=lambda kv: kv[0])[0][1]
    return OpeKeypair.generate("ephemeral")


def _build_inline_jwks() -> Dict[str, Any]:
    """Attempt to build an inline JWKS for inclusion in envelopes.
    Prefers env-driven registry; falls back to local keystore.
    """
    # Try env
    try:
        reg = KeyRegistry.from_env()
        jwks = reg.to_jwks()
        if jwks.get("keys"):
            return jwks
    except Exception:
        pass
    # Fallback to keystore
    ks_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(
        os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json"
    )
    keys = []
    try:
        ks, _active = ensure_keystore_file(ks_path)
        for kid, kp in ks.items():
            raw = kp.public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            x = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
            keys.append({"kty": "OKP", "crv": "Ed25519", "x": x, "kid": kid})
    except Exception:
        pass
    return {"keys": keys}


@router.post("/v1/envelope", tags=["envelope"])
async def make_envelope(payload: Dict[str, Any], request: Request, response: Response):
    sft = get_default_sft()
    oml_c = to_oml_c(payload, sft=sft)
    cid = compute_cid(oml_c)

    kp = _get_signing_keypair()
    ope = sign_over_content(kp, oml_c, oml_cid=cid)
    ope_min = json.dumps(ope, separators=(",", ":"))
    ope_b64u = base64.urlsafe_b64encode(ope_min.encode("utf-8")).decode("ascii").rstrip("=")
    oml_c_b64u = base64.urlsafe_b64encode(oml_c).decode("ascii").rstrip("=")

    jwks_inline = _build_inline_jwks()

    env = ProofEnvelope(
        oml_cid=cid,
        kid=ope.get("kid", kp.kid),
        ope=ope_b64u,
        jwks_url=WELL_KNOWN_ODIN_JWKS_PATH,
        jwks_inline=jwks_inline if jwks_inline.get("keys") else None,
        oml_c_b64=oml_c_b64u,
    )

    # 0.9.0-beta: Extract and process SBOM headers
    sbom_info = extract_sbom_from_request(request)
    record_sbom_metrics(sbom_info)

    # Build base receipt
    receipt = {"payload": payload, "proof": json.loads(env.to_json())}
    
    # 0.9.0-beta: Enhance with SBOM if present
    receipt = enhance_receipt_with_sbom(receipt, sbom_info)

    # 0.9.0-beta: Add per-hop metering and billing
    metering_unit = create_operation_billing("envelope", payload, receipt, sbom_info)
    tenant_id = getattr(request.state, "tenant_id", "default")
    realm_id = getattr(request.state, "realm_id", tenant_id)
    receipt = enhance_receipt_with_marketplace_billing(receipt, metering_unit, realm_id)

    # 0.9.0-beta: Extract trace context and emit telemetry
    trace_context = TraceContext.from_headers(dict(request.headers))
    trace_id = emit_receipt_telemetry(
        receipt, 
        operation="envelope", 
        trace_context=trace_context
    )

    # 0.9.0-beta: Auto-report usage to Stripe (async)
    try:
        await auto_report_stripe_usage(receipt, tenant_id)
    except Exception as e:
        # Don't fail the request if billing fails
        import logging
        logging.getLogger(__name__).warning(f"Failed to report usage: {e}")

    # Surface mesh/trace headers if present (shim behavior for tools that expect them)
    original_trace_id = request.headers.get("X-ODIN-Trace-Id") or trace_id
    hop_id = request.headers.get("X-ODIN-Hop-Id") or None
    fwd = request.headers.get("X-ODIN-Forwarded-By") or None
    try:
        if original_trace_id:
            response.headers["X-ODIN-Trace-Id"] = original_trace_id
        if hop_id:
            response.headers["X-ODIN-Hop-Id"] = hop_id
        if fwd:
            response.headers["X-ODIN-Forwarded-By"] = fwd
        # Add OpenTelemetry trace ID for external correlation
        if trace_id:
            response.headers["X-ODIN-Otel-Trace-Id"] = trace_id
    except Exception:
        pass

    return receipt
