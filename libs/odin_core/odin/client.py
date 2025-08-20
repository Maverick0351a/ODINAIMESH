from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

import httpx

from .constants import X_ODIN_JWKS, ACCEPT_PROOF_HEADER, DEFAULT_ACCEPT_PROOF
from .verifier import verify, VerifyResult
from .discovery import fetch_discovery


@dataclass
class OdinVerification:
    ok: bool
    cid: Optional[str]
    kid: Optional[str]
    reason: Optional[str] = None


class OdinHttpClient:
    """
    Minimal, production-ready HTTP client that:
      - POSTs JSON to ODIN endpoints,
      - extracts 'proof' envelope from response bodies,
      - fetches JWKS (inline or via URL/header),
      - verifies OPE over exact OML-C bytes (recomputes CID),
      - returns the application payload + OdinVerification.
    """

    def __init__(
        self,
        base_url: str,
        *,
        client: Optional[httpx.Client] = None,
        jwks_url: Optional[str] = None,
        jwks_inline: Optional[Dict[str, Any]] = None,
        require_proof: bool = True,
        accept_proof: str = DEFAULT_ACCEPT_PROOF,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.jwks_url = jwks_url
        self.jwks_inline = jwks_inline
        self.require_proof = require_proof
        self.accept_proof = accept_proof
        self._owned_client = client is None
        if client is None:
            default_headers = {ACCEPT_PROOF_HEADER: self.accept_proof} if self.accept_proof else None
            self.client = httpx.Client(base_url=self.base_url, timeout=timeout, headers=default_headers)
        else:
            self.client = client

    def close(self) -> None:
        if self._owned_client:
            self.client.close()

    @classmethod
    def from_discovery(cls, base_url: str, **kwargs) -> "OdinHttpClient":
        """Build a client by fetching discovery.json and using its jwks_url.

        Supports passing a custom httpx.Transport for tests via kwargs["transport"].
        Any other kwargs (e.g., require_proof, accept_proof, timeout) are forwarded.
        """
        transport = kwargs.pop("transport", None)
        disc = fetch_discovery(base_url, transport=transport)
        return cls(base_url, jwks_url=disc.jwks_url, **kwargs)

    # ---------- High-level API ----------------------------------------------

    def post_envelope(
        self, route: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> Tuple[Dict[str, Any], OdinVerification]:
        """
        POSTs to an endpoint that returns {'payload': ..., 'proof': {...}}.
        Verifies the returned proof envelope before returning payload.
        """
        url = self._abs(route)
        # Ensure negotiation header is present without clobbering caller-provided headers
        hdrs: Optional[Dict[str, str]] = headers
        if getattr(self, "accept_proof", None):
            hdrs = (hdrs or {}).copy()
            hdrs.setdefault(ACCEPT_PROOF_HEADER, self.accept_proof)  # type: ignore[arg-type]
        r = self.client.post(url, json=payload, headers=hdrs)
        r.raise_for_status()

        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object")
        if "proof" not in data:
            if self.require_proof:
                raise ValueError("Response missing 'proof' envelope")
            return data, OdinVerification(ok=False, cid=None, kid=None, reason="no proof")

        proof = data["proof"]
        ver = self._verify_envelope(proof, response_headers=r.headers)
        if self.require_proof and not ver.ok:
            raise ValueError(f"ODIN proof verification failed: {ver.reason}")

        # Return the app payload if present; else the whole body
        app_payload = data.get("payload", data)
        return app_payload, ver

    # ---------- Internals ----------------------------------------------------

    def _abs(self, route: str) -> str:
        # Allow absolute URLs or relative paths
        if route.startswith("http://") or route.startswith("https://"):
            return route
        return urljoin(self.base_url, route.lstrip("/"))

    def _resolve_jwks(self, proof: Dict[str, Any], response_headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Resolve JWKS:
          1) client jwks_inline (if configured)
          2) client jwks_url (if configured)
          3) proof['jwks_inline'] if present
          4) proof['jwks_url'] (absolute or relative)
          5) X-ODIN-JWKS response header (absolute or relative)
        """
        # 1) Client-level inline
        if isinstance(getattr(self, "jwks_inline", None), dict) and "keys" in self.jwks_inline:  # type: ignore[attr-defined]
            return self.jwks_inline  # type: ignore[attr-defined]

        # 2) Client-level URL
        if isinstance(getattr(self, "jwks_url", None), str) and self.jwks_url:  # type: ignore[attr-defined]
            return self._fetch_jwks(self.jwks_url)  # type: ignore[arg-type]

        # 3) Inline from envelope
        jwks_inline = proof.get("jwks_inline")
        if isinstance(jwks_inline, dict) and "keys" in jwks_inline:
            return jwks_inline

        # 4) URL in the envelope
        jwks_url = proof.get("jwks_url")
        if isinstance(jwks_url, str) and jwks_url:
            return self._fetch_jwks(jwks_url)

        # 5) Header hint
        hdr_url = response_headers.get(X_ODIN_JWKS)
        if hdr_url:
            return self._fetch_jwks(hdr_url)

        return None

    def _fetch_jwks(self, url_or_path: str) -> Dict[str, Any]:
        # Make relative paths absolute to our base_url
        if url_or_path.startswith("/"):
            url = urljoin(self.base_url, url_or_path.lstrip("/"))
        else:
            url = url_or_path
        r = self.client.get(url)
        r.raise_for_status()
        return r.json()

    def _verify_envelope(self, proof: Dict[str, Any], response_headers: Dict[str, str]) -> OdinVerification:
        """
        Pass a ProofEnvelope dict into core verifier. If no JWKS hint is resolvable,
        rely on embedded pub key only.
        """
        if not isinstance(proof, dict):
            return OdinVerification(ok=False, cid=None, kid=None, reason="invalid_proof_type")

        # Try to resolve JWKS (optional)
        jwks: Optional[Dict[str, Any]]
        try:
            jwks = self._resolve_jwks(proof, response_headers)
        except Exception as e:
            return OdinVerification(ok=False, cid=None, kid=proof.get("kid"), reason=f"jwks:{e}")

        res: VerifyResult = verify(envelope=proof, jwks=jwks)
        return OdinVerification(
            ok=res.ok,
            cid=res.cid,
            kid=res.kid,
            reason=None if res.ok else res.reason,
        )
