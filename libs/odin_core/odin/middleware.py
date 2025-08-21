from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional

from .constants import (
    X_ODIN_OPE,
    X_ODIN_JWKS,
    X_ODIN_PROOF_VERSION,
    ODIN_PROOF_VERSION_VALUE,
    WELL_KNOWN_ODIN_JWKS_PATH,
)


class ProofDiscoveryMiddleware(BaseHTTPMiddleware):
    """
    If a response already includes X-ODIN-OPE (i.e., it carries a signature),
    automatically add:
      - X-ODIN-JWKS: discovery path for public keys
      - X-ODIN-Proof-Version: semantic version for proof format
    Safe to enable globally. Does nothing for non-proof responses.
    """

    def __init__(self, app: ASGIApp, jwks_path: Optional[str] = None) -> None:
        super().__init__(app)
        self._jwks_path = jwks_path or WELL_KNOWN_ODIN_JWKS_PATH

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get(X_ODIN_OPE):
            response.headers.setdefault(X_ODIN_JWKS, self._jwks_path)
            response.headers.setdefault(X_ODIN_PROOF_VERSION, ODIN_PROOF_VERSION_VALUE)
        return response
