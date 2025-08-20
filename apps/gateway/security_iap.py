from __future__ import annotations

import os
from typing import Iterable

from fastapi import HTTPException, Request


def _parse_list(env_val: str | None) -> list[str]:
    if not env_val:
        return []
    return [x.strip().lower() for x in env_val.replace(";", ",").split(",") if x.strip()]


def _email_allowed(email: str, allowed_emails: Iterable[str], allowed_domains: Iterable[str]) -> bool:
    e = email.strip().lower()
    if e in allowed_emails:
        return True
    try:
        dom = e.split("@", 1)[1]
    except Exception:
        return False
    return dom in allowed_domains


def enforce_iap_if_required(request: Request) -> None:
    """Enforce Cloud IAP (or equivalent) identity on admin routes when enabled.

    Behavior:
    - If ODIN_REQUIRE_IAP is not set/enabled, no-op.
    - When enabled, require X-Goog-Authenticated-User-Email header.
    - If ODIN_ADMIN_ALLOWED_EMAILS or ODIN_ADMIN_ALLOWED_DOMAINS are set, enforce allow-list.
    """
    if os.getenv("ODIN_REQUIRE_IAP", "0") not in ("1", "true", "True"):  # opt-in only
        return

    email = (
        request.headers.get("X-Goog-Authenticated-User-Email")
        or request.headers.get("x-goog-authenticated-user-email")
        or ""
    )
    # Header may carry a prefix like "accounts.google.com:alice@example.com"
    if ":" in email:
        email = email.split(":", 1)[1]
    email = email.strip()
    if not email:
        raise HTTPException(status_code=403, detail="iap_required")

    allow_emails = _parse_list(os.getenv("ODIN_ADMIN_ALLOWED_EMAILS"))
    allow_domains = _parse_list(os.getenv("ODIN_ADMIN_ALLOWED_DOMAINS"))
    if allow_emails or allow_domains:
        if not _email_allowed(email, allow_emails, allow_domains):
            raise HTTPException(status_code=403, detail="iap_email_not_allowed")
