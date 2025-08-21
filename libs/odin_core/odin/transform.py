from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Union
import base64
import hashlib
import json

from blake3 import blake3

# Use relative imports within the odin package
from .ope import OpeKeypair, sign_over_content
from .envelope import ProofEnvelope


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _canon(obj: Any) -> bytes:
    """Deterministic canonical JSON for hashing/signing transform subjects."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def _sha256_b64u(b: bytes) -> str:
    return _b64u(hashlib.sha256(b).digest())


def _b3_b64u(b: bytes) -> str:
    return _b64u(blake3(b).digest())


@dataclass
class TransformSubject:
    v: int
    type: str  # "transform"
    sft_from: str
    sft_to: str
    input_sha256_b64u: str
    output_sha256_b64u: str
    map_id: str
    map_sha256_b64u: str
    out_oml_cid: Optional[str] = None  # if known (ties to response envelope)


@dataclass
class TransformReceipt:
    v: int
    subject: Dict[str, Any]  # TransformSubject as dict
    linkage_hash_b3_256_b64u: str
    envelope: Dict[str, Any]  # ProofEnvelope as dict (over subject bytes)


def build_transform_subject(
    *,
    input_obj: Any,
    output_obj: Any,
    sft_from: str,
    sft_to: str,
    map_obj_or_bytes: Union[Dict[str, Any], bytes],
    map_id: str,
    out_oml_cid: Optional[str] = None,
) -> TransformSubject:
    in_bytes = _canon(input_obj)
    out_bytes = _canon(output_obj)
    if isinstance(map_obj_or_bytes, (bytes, bytearray, memoryview)):
        map_bytes = bytes(map_obj_or_bytes)
    else:
        map_bytes = _canon(map_obj_or_bytes)

    return TransformSubject(
        v=1,
        type="transform",
        sft_from=sft_from,
        sft_to=sft_to,
        input_sha256_b64u=_sha256_b64u(in_bytes),
        output_sha256_b64u=_sha256_b64u(out_bytes),
        map_id=map_id,
        map_sha256_b64u=_sha256_b64u(map_bytes),
        out_oml_cid=out_oml_cid,
    )


def sign_transform_receipt(
    *,
    subject: TransformSubject,
    keypair: Optional[OpeKeypair] = None,
    jwks_url: Optional[str] = None,
    jwks_inline: Optional[Dict[str, Any]] = None,
    include_subject_b64: bool = True,
) -> TransformReceipt:
    """Create a signed TransformReceipt binding input/map/output via linkage hash and envelope.

    Requires an OpeKeypair to sign the canonicalized TransformSubject bytes. The envelope's
    OML CID will be computed over those canonical bytes for consistency with existing verifiers.
    """
    # Linkage hash binds input, map, output using a delimiter to avoid ambiguity
    in_d = base64.urlsafe_b64decode(subject.input_sha256_b64u + "==")
    map_d = base64.urlsafe_b64decode(subject.map_sha256_b64u + "==")
    out_d = base64.urlsafe_b64decode(subject.output_sha256_b64u + "==")
    linkage = _b3_b64u(in_d + b"\x1f" + map_d + b"\x1f" + out_d)

    # Canonical subject bytes are the exact message covered by OPE signature
    subj_bytes = _canon(asdict(subject))

    # Sign with provided keypair (or generate a one-off for convenience)
    kp = keypair or OpeKeypair.generate("k1")
    ope = sign_over_content(kp, subj_bytes, None)

    # Wrap as ProofEnvelope for standard downstream verification
    env = ProofEnvelope.from_ope(
        subj_bytes,
        ope=ope,
        jwks_url=jwks_url,
        jwks_inline=jwks_inline,
        include_oml_c_b64=include_subject_b64,
    )

    # Convert envelope dataclass → dict
    env_dict: Dict[str, Any] = {
        "oml_cid": env.oml_cid,
        "kid": env.kid,
        "ope": env.ope,
        "jwks_url": env.jwks_url,
        "jwks_inline": env.jwks_inline,
        "oml_c_b64": env.oml_c_b64,
        "sft_id": env.sft_id,
    }

    return TransformReceipt(
        v=1,
        subject=asdict(subject),
        linkage_hash_b3_256_b64u=linkage,
        envelope=env_dict,
    )
