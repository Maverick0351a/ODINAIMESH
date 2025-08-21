from __future__ import annotations

import os
from fastapi import APIRouter, Depends, HTTPException, Request

from .runtime import reload_policy, reload_sft_maps
from .security_iap import enforce_iap_if_required
from .dynamic_runtime import dynamic_force_reload, dynamic_status  # type: ignore

router = APIRouter(tags=["admin"], prefix="/v1/admin")


def _require_admin(request: Request):
    """
    Minimal guard:
      - Endpoint is available only when ODIN_ENABLE_ADMIN=1
      - Optional shared secret header X-Admin-Token must match ODIN_ADMIN_TOKEN (if set)
    """
    # Optional IAP/SSO enforcement (allow-list via env); no-op unless enabled
    try:
        enforce_iap_if_required(request)
    except HTTPException:
        # surface as-is
        raise
    if os.getenv("ODIN_ENABLE_ADMIN", "0") not in ("1", "true", "True"):
        raise HTTPException(status_code=404, detail="admin disabled")

    token_req = request.headers.get("X-Admin-Token")
    token_env = os.getenv("ODIN_ADMIN_TOKEN")
    if token_env and token_req != token_env:
        raise HTTPException(status_code=401, detail="admin token invalid")


@router.post("/reload/policy", dependencies=[Depends(_require_admin)])
def admin_reload_policy():
    return reload_policy()


@router.post("/reload/maps", dependencies=[Depends(_require_admin)])
def admin_reload_maps():
    return reload_sft_maps()


@router.get("/dynamic/status", dependencies=[Depends(_require_admin)])
def admin_dynamic_status():
    st = dynamic_status()
    return st or {"enabled": False}


@router.post("/dynamic/reload/{target}", dependencies=[Depends(_require_admin)])
def admin_dynamic_reload(target: str):
    st = dynamic_force_reload(target)
    if st is None:
        return {"enabled": False}
    return st
