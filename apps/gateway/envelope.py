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
def make_envelope(payload: Dict[str, Any], request: Request, response: Response):
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

    # Surface mesh/trace headers if present (shim behavior for tools that expect them)
    trace_id = request.headers.get("X-ODIN-Trace-Id") or None
    hop_id = request.headers.get("X-ODIN-Hop-Id") or None
    fwd = request.headers.get("X-ODIN-Forwarded-By") or None
    try:
        if trace_id:
            response.headers["X-ODIN-Trace-Id"] = trace_id
        if hop_id:
            response.headers["X-ODIN-Hop-Id"] = hop_id
        if fwd:
            response.headers["X-ODIN-Forwarded-By"] = fwd
    except Exception:
        pass

    return {"payload": payload, "proof": json.loads(env.to_json())}
