from __future__ import annotations

from fastapi import APIRouter, Body, Request, HTTPException

# Use the project-local odin module path
from libs.odin_core.odin.dynamic_reload import make_reloader, require_admin  # type: ignore
from .security_iap import enforce_iap_if_required

admin_router = APIRouter(prefix="/v1/admin", tags=["admin"])


def attach_reloader(app) -> None:
    """Attach a global dynamic reloader to app.state if not already set.

    This mirrors the provided snippet but guards against optional backends
    not being available (e.g., GCS libs) so tests don't fail on import.
    """
    if getattr(app.state, "reloader", None) is not None:
        return
    try:
        app.state.reloader = make_reloader()
    except Exception:
        # Leave unset if dynamic reload cannot be constructed in this env
        app.state.reloader = None


@admin_router.post("/reload")
def admin_reload(request: Request, target: str = Body(default="all", embed=True)):
    # Optional IAP/SSO header enforcement
    try:
        enforce_iap_if_required(request)
    except HTTPException:
        raise
    try:
        require_admin(request.headers)  # validates x-odin-admin-key
    except PermissionError:
        raise HTTPException(status_code=403, detail="forbidden")

    reloader = getattr(request.app.state, "reloader", None)
    if reloader is None:
        raise HTTPException(status_code=503, detail="reloader_unavailable")
    try:
        from apps.gateway.metrics import dynamic_reload_total as _dyn
        _dyn.labels(target=target or "all").inc()
    except Exception:
        pass

    # Also reload the realm pack
    try:
        from apps.gateway.pack_loader import realm_pack_loader
        import os
        pack_uri = os.getenv("ODIN_REALM_PACK_URI")
        if pack_uri:
            realm_pack_loader.load_pack(pack_uri)
    except Exception as e:
        # Log the error but don't fail the request
        import logging
        logging.getLogger(__name__).error(f"Failed to reload realm pack: {e}")

    return reloader.force_reload(target)


@admin_router.get("/reload/status")
def reload_status(request: Request):
    # Optional IAP/SSO header enforcement
    try:
        enforce_iap_if_required(request)
    except HTTPException:
        raise
    try:
        require_admin(request.headers)
    except PermissionError:
        raise HTTPException(status_code=403, detail="forbidden")

    reloader = getattr(request.app.state, "reloader", None)
    if reloader is None:
        raise HTTPException(status_code=503, detail="reloader_unavailable")
    return reloader.status()
