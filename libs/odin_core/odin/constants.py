from __future__ import annotations

from typing import Final

# Proof headers (already emitted by /v1/translate)
X_ODIN_OML_CID: Final[str] = "X-ODIN-OML-CID"
X_ODIN_OML_C_PATH: Final[str] = "X-ODIN-OML-C-Path"
X_ODIN_OPE: Final[str] = "X-ODIN-OPE"
X_ODIN_OPE_KID: Final[str] = "X-ODIN-OPE-KID"

# Discovery / versioning
X_ODIN_JWKS: Final[str] = "X-ODIN-JWKS"
X_ODIN_PROOF_VERSION: Final[str] = "X-ODIN-Proof-Version"
ODIN_PROOF_VERSION_VALUE: Final[str] = "1"
WELL_KNOWN_ODIN_JWKS_PATH: Final[str] = "/.well-known/odin/jwks.json"

# Proof negotiation
ACCEPT_PROOF_HEADER: Final[str] = "X-ODIN-Accept-Proof"
DEFAULT_ACCEPT_PROOF: Final[str] = "embed,headers"

# Environment variables controlling key publication / verification
ENV_JWKS_JSON: Final[str] = "ODIN_OPE_JWKS"          # inline JWKS JSON (string)
ENV_JWKS_PATH: Final[str] = "ODIN_OPE_JWKS_PATH"     # filesystem path to JWKS JSON
ENV_SINGLE_PUBKEY: Final[str] = "ODIN_OPE_PUBKEY"    # single Ed25519 pubkey (hex/base64/base64url)
ENV_SINGLE_PUBKEY_KID: Final[str] = "ODIN_OPE_KID"   # kid for single-key publication

# Data directory for persisted artifacts (receipts, OML blobs)
ENV_DATA_DIR: Final[str] = "ODIN_DATA_DIR"           # default: tmp/odin
DEFAULT_DATA_DIR: Final[str] = "tmp/odin"

__all__ = [
    "X_ODIN_OML_CID",
    "X_ODIN_OML_C_PATH",
    "X_ODIN_OPE",
    "X_ODIN_OPE_KID",
    "X_ODIN_JWKS",
    "X_ODIN_PROOF_VERSION",
    "ODIN_PROOF_VERSION_VALUE",
    "WELL_KNOWN_ODIN_JWKS_PATH",
    "ACCEPT_PROOF_HEADER",
    "DEFAULT_ACCEPT_PROOF",
    "ENV_JWKS_JSON",
    "ENV_JWKS_PATH",
    "ENV_SINGLE_PUBKEY",
    "ENV_SINGLE_PUBKEY_KID",
    "ENV_DATA_DIR",
    "DEFAULT_DATA_DIR",
]
