"""
ODIN Proof Envelope

A compact, portable JSON object bundling:
- oml_cid
- kid
- ope (base64url)
- jwks (optional inline keys OR URL hint)
- oml_c_b64 (optional; base64url of canonical OML-C bytes)

This can travel in logs, receipts, or API responses.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .cid import compute_cid


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


@dataclass
class ProofEnvelope:
    oml_cid: str
    kid: str
    ope: str
    jwks_url: Optional[str] = None
    jwks_inline: Optional[Dict[str, Any]] = None
    oml_c_b64: Optional[str] = None
    sft_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_parts(
        cls,
        oml_c_bytes: bytes,
        kid: str,
        sig_b: bytes,
        jwks_url: Optional[str] = None,
        jwks_inline: Optional[Dict[str, Any]] = None,
        include_oml_c_b64: bool = False,
    sft_id: Optional[str] = None,
    ) -> "ProofEnvelope":
        cid = compute_cid(oml_c_bytes)
        b64sig = _b64url(sig_b)
        return cls(
            oml_cid=cid,
            kid=kid,
            ope=b64sig,
            jwks_url=jwks_url,
            jwks_inline=jwks_inline,
            oml_c_b64=_b64url(oml_c_bytes) if include_oml_c_b64 else None,
            sft_id=sft_id,
        )

    @classmethod
    def from_ope(
        cls,
        oml_c_bytes: bytes,
        ope: Dict[str, Any],
        *,
        jwks_url: Optional[str] = None,
        jwks_inline: Optional[Dict[str, Any]] = None,
        include_oml_c_b64: bool = False,
    sft_id: Optional[str] = None,
    ) -> "ProofEnvelope":
        """Construct from a full OPE JSON dict. The 'ope' field will be the base64url of the compact JSON."""
        cid = compute_cid(oml_c_bytes)
        kid = str(ope.get("kid", ""))
        raw = json.dumps(ope, separators=(",", ":")).encode("utf-8")
        ope_b64u = _b64url(raw)
        return cls(
            oml_cid=cid,
            kid=kid,
            ope=ope_b64u,
            jwks_url=jwks_url,
            jwks_inline=jwks_inline,
            oml_c_b64=_b64url(oml_c_bytes) if include_oml_c_b64 else None,
            sft_id=sft_id,
        )
