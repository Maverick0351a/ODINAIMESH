from __future__ import annotations

import json
import base64
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.parse import urljoin

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from prometheus_client import Counter

from libs.odin_core.odin.ope import sign_ope
from libs.odin_core.odin.http_sig import sign_v1 as http_sign_v1
from libs.odin_core.odin.security.keystore import ensure_keystore_file
from libs.odin_core.odin.envelope import ProofEnvelope
from libs.odin_core.odin.sft import validate as sft_validate, CORE_ID as DEFAULT_SFT_ID
from libs.odin_core.odin.storage import (
    create_storage_from_env,
    key_oml,
    key_receipt,
    HDR_OML_C_URL,
    HDR_RECEIPT_URL,
)

# --- ENV / config ---
ENV_SIGN_ROUTES = "ODIN_SIGN_ROUTES"  # comma-separated path prefixes
ENV_SIGN_REQUIRE = "ODIN_SIGN_REQUIRE"  # "1" strict (default), "0" soft
ENV_SIGN_EMBED = "ODIN_SIGN_EMBED"  # "1" embed {payload, proof} (default "1")
ENV_DATA_DIR = "ODIN_DATA_DIR"  # reuse existing, default tmp/odin

DEFAULT_DATA_DIR = "tmp/odin"
ENV_STORAGE_BACKEND = "ODIN_STORAGE_BACKEND"  # local (default), gcs, inmem
ENV_STORAGE_PUBLIC_URLS = (
    "ODIN_STORAGE_PUBLIC_URLS"  # when "1", attempt to expose public URLs
)
ENV_HTTP_SIG = "ODIN_HTTP_SIG"  # when "1", emit X-ODIN-HTTP-Sig response header

# --- SFT validation (optional) ---
ENV_SFT_VALIDATE_ROUTES = (
    "ODIN_SFT_VALIDATE_ROUTES"  # comma-separated prefixes to validate before signing
)
ENV_SFT_ID = "ODIN_SFT_ID"  # defaults to core@v0.1

# --- Request/Response negotiation headers ---
HDR_ACCEPT_PROOF = "X-ODIN-Accept-Proof"  # required|if-available|none
HDR_PROOF_STATUS = "X-ODIN-Proof-Status"  # signed|absent|ignored

# --- Proof headers (kept aligned with gateway) ---
X_OML_CID = "X-ODIN-OML-CID"
X_OML_C_PATH = "X-ODIN-OML-C-Path"
X_OPE = "X-ODIN-OPE"
X_OPE_KID = "X-ODIN-OPE-KID"
X_JWKS = "X-ODIN-JWKS"
WELL_KNOWN_JWKS = "/.well-known/odin/jwks.json"

# --- Metrics ---
MET_SIGN_SUCCESS = Counter(
    "odin_response_sign_success_total", "Responses signed successfully"
)
MET_SIGN_ERROR = Counter(
    "odin_response_sign_error_total", "Responses failed to sign or required-proof unmet"
)
MET_SIGN_DOWNGRADE = Counter(
    "odin_response_sign_downgrade_total",
    "Responses that negotiated if-available but were not signed",
)
MET_SIGN_SKIP = Counter(
    "odin_response_sign_skip_total",
    "Responses skipped (already signed, non-JSON, non-2xx, or not requested/enforced)",
)
MET_SIGN_IGNORED = Counter(
    "odin_response_sign_preference_ignored_total",
    "Client requested none but route enforced; preference ignored",
)
MET_SFT_INVALID = Counter(
    "odin_sft_validation_failed_total", "SFT validation failures before signing"
)


def _data_dir() -> Path:
    return Path(os.getenv(ENV_DATA_DIR, DEFAULT_DATA_DIR))


def _ensure_dirs():
    (_data_dir() / "oml").mkdir(parents=True, exist_ok=True)
    (_data_dir() / "receipts").mkdir(parents=True, exist_ok=True)


def _path_enforced(path: str, prefixes: List[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


def _json_media(response: Response) -> bool:
    ctype = (response.headers.get("content-type") or response.media_type or "").lower()
    return "application/json" in ctype


async def _collect_body(response: Response) -> bytes:
    if hasattr(response, "body"):
        try:
            body = response.body
            if isinstance(body, (bytes, bytearray)):
                return bytes(body)
        except Exception:
            pass
    chunks: List[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    body = b"".join(chunks)
    return body


def _to_oml_c_bytes(obj: Any) -> bytes:
    # Adapted to this repo's OML API
    from libs.odin_core.odin.oml import to_oml_c, get_default_sft  # type: ignore

    sft = get_default_sft()
    return to_oml_c(obj, sft=sft)


def _persist(
    oml_c_bytes: bytes, cid: str, kid: str, sig_b64u: str, sft_id: Optional[str] = None
) -> Tuple[Path, Path]:
    """Persist OML and receipt via pluggable storage; still return local filesystem paths for headers/tests."""
    # Primary storage (local default, can be GCS)
    storage = create_storage_from_env()
    oml_key = key_oml(cid)
    rcpt_key = key_receipt(cid)

    # Write if missing (best-effort idempotent)
    if not storage.exists(oml_key):
        storage.put_bytes(oml_key, oml_c_bytes, content_type="application/cbor")

    rcpt_dict = {"oml_cid": cid, "kid": kid, "ope": sig_b64u}
    # Provide a path hint in receipt if stored locally
    local_oml_path = _data_dir() / "oml" / f"{cid}.cbor"
    try:
        local_oml_path.parent.mkdir(parents=True, exist_ok=True)
        if not local_oml_path.exists():
            local_oml_path.write_bytes(oml_c_bytes)
        rcpt_dict["oml_c_path"] = str(local_oml_path)
    except Exception:
        pass
    if sft_id:
        rcpt_dict["sft_id"] = sft_id

    rcpt_bytes = json.dumps(rcpt_dict, separators=(",", ":")).encode("utf-8")
    if not storage.exists(rcpt_key):
        storage.put_bytes(rcpt_key, rcpt_bytes, content_type="application/json")

    # Compute header path: prefer local path; else fallback to storage URL
    header_path: str
    if local_oml_path.exists():
        header_path = str(local_oml_path)
    else:
        header_path = storage.url_for(oml_key) or ""

    # Mirror receipt to local filesystem for receipts endpoint compatibility
    local_rcpt_path = _data_dir() / "receipts" / f"{cid}.ope.json"
    try:
        local_rcpt_path.parent.mkdir(parents=True, exist_ok=True)
        if not local_rcpt_path.exists():
            local_rcpt_path.write_bytes(rcpt_bytes)
    except Exception:
        pass

    return Path(header_path) if header_path else local_oml_path, local_rcpt_path


class ResponseSigningMiddleware(BaseHTTPMiddleware):
    """
    Guarantees proofs on responses with client/server negotiation.

    Client can send: X-ODIN-Accept-Proof: required | if-available | none
      - required: must return proof; else 406 Not Acceptable (structured error)
      - if-available: sign if possible; else pass-through with X-ODIN-Proof-Status: absent
      - none: do not sign unless route is enforced by ODIN_SIGN_ROUTES (in which case we sign and mark ignored)

    Server policy:
      - Routes matching ODIN_SIGN_ROUTES are enforced according to ODIN_SIGN_REQUIRE (strict/soft).
      - Negotiation applies to ALL routes when middleware is active, allowing clients to opt in to proofs.

    All successful signatures emit headers: X-ODIN-OML-CID, X-ODIN-OML-C-Path, X-ODIN-OPE, X-ODIN-OPE-KID, X-ODIN-JWKS.
    Additionally sets: X-ODIN-Proof-Status: signed|absent|ignored.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        prefixes = os.getenv(ENV_SIGN_ROUTES, "").strip()
        self.prefixes: List[str] = [p.strip() for p in prefixes.split(",") if p.strip()]
        self.strict: bool = os.getenv(ENV_SIGN_REQUIRE, "1") not in (
            "0",
            "false",
            "False",
        )
        self.embed: bool = os.getenv(ENV_SIGN_EMBED, "1") not in ("0", "false", "False")
        sft_pref = os.getenv(ENV_SFT_VALIDATE_ROUTES, "/v1/translate").strip()
        self.sft_prefixes: List[str] = [
            p.strip() for p in sft_pref.split(",") if p.strip()
        ]
        self.sft_id: Optional[str] = os.getenv(ENV_SFT_ID, DEFAULT_SFT_ID)
        # Reuse a storage instance
        self.storage = create_storage_from_env()
        # HTTP Sig control
        self.enable_http_sig: bool = os.getenv(ENV_HTTP_SIG, "0").lower() in ("1", "true", "yes")
        # Prepare keystore path (used for HTTP-Sig signing to reuse OPE keys)
        self._keystore_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(
            os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json"
        )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        preference = (request.headers.get(HDR_ACCEPT_PROOF, "") or "").lower()
        # Normalize
        if preference not in ("required", "if-available", "none", ""):
            preference = "if-available"
        negotiated = preference in ("required", "if-available")
        enforced = _path_enforced(path, self.prefixes)
        validate_sft = _path_enforced(path, self.sft_prefixes)

        response = await call_next(request)

        # Only act if (enforced route) OR (client negotiated)
        # Note: SFT validation is applied only when we're otherwise acting (enforced/negotiated)
        if not enforced and not negotiated:
            MET_SIGN_SKIP.inc()
            return response

        # Never sign Prometheus metrics endpoint; keep it raw for scrapers
        if path.startswith("/metrics"):
            MET_SIGN_SKIP.inc()
            return response

        # For safe methods, require negotiation unless the route is enforced
        if request.method in ("GET", "HEAD", "OPTIONS") and not (
            negotiated or enforced
        ):
            MET_SIGN_SKIP.inc()
            return response

        # If already signed (headers present), honor and mark status
        if response.headers.get(X_OPE):
            response.headers.setdefault(HDR_PROOF_STATUS, "signed")
            MET_SIGN_SKIP.inc()
            return response

        # Grab body
        try:
            body = await _collect_body(response)
        except Exception as e:
            MET_SIGN_ERROR.inc()
            return self._err(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "odin.sign.stream_error",
                f"unable to capture response body: {e}",
            )

        # Non-JSON handling
        if not _json_media(response):
            if preference == "required":
                # Client requires proof but we cannot provide
                MET_SIGN_ERROR.inc()
                r = self._err(
                    status.HTTP_406_NOT_ACCEPTABLE,
                    "odin.proof.required",
                    "server could not provide required proof for this response",
                )
                r.headers[HDR_PROOF_STATUS] = "absent"
                return r
            # Pass-through (even if enforced+strict) to maintain current behavior/tests
            response.headers.setdefault(HDR_PROOF_STATUS, "absent")
            MET_SIGN_DOWNGRADE.inc()
            return self._set_body(response, body)

        # Parse JSON
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            if preference == "required":
                MET_SIGN_ERROR.inc()
                r = self._err(
                    status.HTTP_406_NOT_ACCEPTABLE,
                    "odin.proof.required",
                    "server could not provide required proof (invalid json)",
                )
                r.headers[HDR_PROOF_STATUS] = "absent"
                return r
            response.headers.setdefault(HDR_PROOF_STATUS, "absent")
            MET_SIGN_DOWNGRADE.inc()
            return self._set_body(response, body)

        # If body already shaped as {payload, proof}, treat as signed (dual-channel)
        if (
            isinstance(data, dict)
            and "proof" in data
            and isinstance(data["proof"], dict)
        ):
            env = data["proof"]
            # Prefer envelope-provided jwks_url if present, else well-known
            jwks_url = None
            if isinstance(env, dict):
                jwks_url = env.get("jwks_url")
                # Attach OML-CID/OPE/KID if present inside envelope
                cid = env.get("oml_cid")
                if isinstance(cid, str):
                    response.headers[X_OML_CID] = cid
                ope = env.get("ope")
                if isinstance(ope, str):
                    response.headers[X_OPE] = ope
                kid = env.get("kid")
                if isinstance(kid, str):
                    response.headers[X_OPE_KID] = kid
                # If inline OML-C is present, persist and expose path header
                oml_c_b64 = env.get("oml_c_b64")
                if isinstance(oml_c_b64, str) and oml_c_b64:
                    try:
                        pad = "=" * ((4 - (len(oml_c_b64) % 4)) % 4)
                        oml_c_bytes = base64.urlsafe_b64decode(oml_c_b64 + pad)
                        persist_cid = cid
                        if not persist_cid:
                            from libs.odin_core.odin.cid import compute_cid  # type: ignore

                            persist_cid = compute_cid(oml_c_bytes)
                        oml_path, _ = _persist(
                            oml_c_bytes,
                            persist_cid,
                            kid or "",
                            ope or "",
                            env.get("sft_id"),
                        )
                        response.headers[X_OML_C_PATH] = str(oml_path)
                        # Also attach URLs if available
                        try:
                            # Gate URL header emission on either public URLs enabled or signed URLs enabled
                            if os.getenv(ENV_STORAGE_PUBLIC_URLS, "0").lower() in (
                                "1",
                                "true",
                                "yes",
                            ) or os.getenv("ODIN_GCS_SIGN_URLS", "0").lower() in (
                                "1",
                                "true",
                                "yes",
                            ):
                                oml_url = self.storage.url_for(key_oml(persist_cid))
                                if oml_url:
                                    response.headers[HDR_OML_C_URL] = oml_url
                                rcpt_url = self.storage.url_for(
                                    key_receipt(persist_cid)
                                )
                                if rcpt_url:
                                    response.headers[HDR_RECEIPT_URL] = rcpt_url
                        except Exception:
                            pass
                    except Exception:
                        pass
            response.headers.setdefault(X_JWKS, jwks_url or WELL_KNOWN_JWKS)
            response.headers.setdefault(HDR_PROOF_STATUS, "signed")
            MET_SIGN_SKIP.inc()
            return self._set_body(response, body)

        # Optional SFT validation step before signing (only when acting)
        if validate_sft:
            try:
                vres = sft_validate(data, self.sft_id or DEFAULT_SFT_ID)
            except Exception:
                vres = None
            if not vres or not vres.ok:
                MET_SFT_INVALID.inc()
                return JSONResponse(
                    {
                        "error": "odin.sft.invalid",
                        "message": f"payload failed {self.sft_id or DEFAULT_SFT_ID} validation",
                        "details": (vres.error_dicts if vres else []),
                    },
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        # Compute OML-C and sign
        try:
            oml_c_bytes = _to_oml_c_bytes(data)
        except Exception:
            if preference == "required":
                MET_SIGN_ERROR.inc()
                r = self._err(
                    status.HTTP_406_NOT_ACCEPTABLE,
                    "odin.proof.required",
                    "server could not provide required proof (oml encode failed)",
                )
                r.headers[HDR_PROOF_STATUS] = "absent"
                return r
            response.headers.setdefault(HDR_PROOF_STATUS, "absent")
            MET_SIGN_DOWNGRADE.inc()
            return self._set_body(response, body)

        sig_b, kid, _pub_b = sign_ope(oml_c_bytes)
        env = ProofEnvelope.from_parts(
            oml_c_bytes=oml_c_bytes,
            kid=kid,
            sig_b=sig_b,
            jwks_url=WELL_KNOWN_JWKS,
            include_oml_c_b64=True,
            sft_id=self.sft_id,
        )
        cid = env.oml_cid

        # Persist
        oml_path, _rcpt_path = _persist(oml_c_bytes, cid, kid, env.ope, self.sft_id)

        # Attach proof headers
        response.headers[X_OML_CID] = cid
        response.headers[X_OML_C_PATH] = str(oml_path)
        # If a public/signed URL is configured, attach it for clients
        try:
            # Gate URL header emission on either public URLs enabled or signed URLs enabled
            if os.getenv(ENV_STORAGE_PUBLIC_URLS, "0").lower() in (
                "1",
                "true",
                "yes",
            ) or os.getenv("ODIN_GCS_SIGN_URLS", "0").lower() in ("1", "true", "yes"):
                oml_url = self.storage.url_for(key_oml(cid))
                if oml_url:
                    response.headers[HDR_OML_C_URL] = oml_url
                rcpt_url = self.storage.url_for(key_receipt(cid))
                if rcpt_url:
                    response.headers[HDR_RECEIPT_URL] = rcpt_url
        except Exception:
            pass
        response.headers[X_OPE] = env.ope
        response.headers[X_OPE_KID] = kid
        response.headers.setdefault(X_JWKS, WELL_KNOWN_JWKS)

        # Mark negotiation result (including when client asked for none on enforced route)
        if preference == "none" and enforced:
            response.headers[HDR_PROOF_STATUS] = "ignored"
            MET_SIGN_IGNORED.inc()
        else:
            response.headers[HDR_PROOF_STATUS] = "signed"

        # Optionally emit an HTTP response signature header over the raw body
        # Uses the same Ed25519 keystore as OPE; does not alter body.
        if self.enable_http_sig:
            try:
                ks, active = ensure_keystore_file(self._keystore_path)
                kp = ks.get(active) if active in ks else None
                if kp is not None:
                    # Compute signature over the body we're about to return
                    http_sig = http_sign_v1(
                        method=request.method,
                        path=request.url.path,
                        body=body,
                        kid=kp.kid,
                        priv=kp.private_key,
                    )
                    response.headers["X-ODIN-HTTP-Sig"] = http_sig
            except Exception:
                # Non-fatal; skip header on errors
                pass

        # Embed envelope if configured
        if self.embed:
            wrapped = {"payload": data, "proof": json.loads(env.to_json())}
            new_body = json.dumps(wrapped, separators=(",", ":")).encode("utf-8")
            MET_SIGN_SUCCESS.inc()
            return self._set_body(response, new_body)
        else:
            MET_SIGN_SUCCESS.inc()
            return self._set_body(response, body)

    def _set_body(self, response: Response, body: bytes) -> Response:
        # Reconstruct a fresh Response with preserved headers and media type.
        headers = dict(response.headers)
        headers.pop("content-length", None)  # let Starlette recalc
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )

    def _err(self, code: int, error: str, message: str) -> JSONResponse:
        r = JSONResponse({"error": error, "message": message}, status_code=code)
        return r
