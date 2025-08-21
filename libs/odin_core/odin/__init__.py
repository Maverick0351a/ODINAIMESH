# path: libs/odin_core/odin/__init__.py
"""
ODIN core package.

Exports OML encode/decode, CID computation, OPE signing/verification, and key management.
"""
from .oml.encoder import to_oml_c, from_oml_c, compute_cid
from .ope import OpeKeypair, sign_over_content, verify_over_content
from .client import OdinHttpClient, OdinVerification
from .transform import (
    TransformSubject,
    TransformReceipt,
    build_transform_subject,
    sign_transform_receipt,
)
from .discovery import Discovery, discovery_url, fetch_discovery
from .http_signing import body_sha256_b64u, build_http_signing_message
from .sft_discovery import DISCOVERY_ID, validate_service_advert, validate_service_find
from .registry_store import RegistryStore, InMemoryRegistry, FirestoreRegistry, create_registry_from_env
from .router_id import get_router_id, new_trace_id, append_forwarded_by, hop_number
from .redaction import apply_redactions

__all__ = [
    "to_oml_c",
    "from_oml_c",
    "compute_cid",
    "OpeKeypair",
    "sign_over_content",
    "verify_over_content",
    "OdinHttpClient",
    "OdinVerification",
    "Discovery",
    "discovery_url",
    "fetch_discovery",
    "TransformSubject",
    "TransformReceipt",
    "build_transform_subject",
    "sign_transform_receipt",
    "body_sha256_b64u",
    "build_http_signing_message",
    "DISCOVERY_ID",
    "validate_service_advert",
    "validate_service_find",
    "RegistryStore",
    "InMemoryRegistry",
    "FirestoreRegistry",
    "create_registry_from_env",
    "get_router_id",
    "new_trace_id",
    "append_forwarded_by",
    "hop_number",
    "apply_redactions",
]
