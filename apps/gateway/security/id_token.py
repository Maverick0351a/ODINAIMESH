from __future__ import annotations

import os
from typing import Optional

# Optional Google Cloud ID token helper. Returns None if not available.
# Attempts to use google-auth compute engine metadata or IDTokenCredentials.
async def maybe_get_id_token(audience_or_url: str, audience_override: Optional[str] = None) -> Optional[str]:
    aud = audience_override or audience_or_url
    # If library unavailable or running outside GCP, return None gracefully.
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.id_token import fetch_id_token
    except Exception:
        return None
    try:
        # Normalize audience: if given a URL, Google expects the base URL for Cloud Run
        # Caller may pass explicit audience via env; prefer that.
        req = Request()
        token = fetch_id_token(req, aud)
        return token
    except Exception:
        return None
