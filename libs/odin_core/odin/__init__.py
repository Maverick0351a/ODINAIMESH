# path: libs/odin_core/odin/__init__.py
"""
ODIN core package.

Exports OML encode/decode, CID computation, OPE signing/verification, and key management.
"""
from .oml.encoder import to_oml_c, from_oml_c, compute_cid
from .ope import OpeKeypair, sign_over_content, verify_over_content

__all__ = [
    "to_oml_c",
    "from_oml_c",
    "compute_cid",
    "OpeKeypair",
    "sign_over_content",
    "verify_over_content",
]
