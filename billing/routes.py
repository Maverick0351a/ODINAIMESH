from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    import stripe  # type: ignore
except Exception:
    stripe = None  # type: ignore


router = APIRouter(prefix="/billing", tags=["billing"])


class CreateCheckoutSessionIn(BaseModel):
    plan: str  # "pro" | "pro_plus"


def _require_stripe():
    if stripe is None:
        raise HTTPException(status_code=500, detail="stripe_not_installed")
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="missing_STRIPE_API_KEY")
    stripe.api_key = api_key
    return stripe


def _get_price_ids():
    return {
        "pro": os.getenv("STRIPE_PRICE_PRO_MONTHLY"),
        "pro_plus": os.getenv("STRIPE_PRICE_PRO_PLUS_MONTHLY"),
        "overage_pro_1k": os.getenv("STRIPE_PRICE_PRO_OVERAGE_1K"),
        "overage_pro_plus_1k": os.getenv("STRIPE_PRICE_PRO_PLUS_OVERAGE_1K"),
        "enterprise_pilot_6mo": os.getenv("STRIPE_PRICE_ENTERPRISE_PILOT_6MO"),
    }


@router.post("/create_checkout_session")
async def create_checkout_session(body: CreateCheckoutSessionIn):
    s = _require_stripe()
    prices = _get_price_ids()
    key = "pro" if body.plan == "pro" else "pro_plus" if body.plan == "pro_plus" else None
    if not key:
        raise HTTPException(status_code=400, detail="invalid_plan")
    base_price = prices.get(key)
    if not base_price:
        raise HTTPException(status_code=500, detail=f"missing_price_id_for_{key}")

    success_url = os.getenv("STRIPE_SUCCESS_URL") or "http://localhost:8080/billing/success"
    cancel_url = os.getenv("STRIPE_CANCEL_URL") or "http://localhost:8080/billing/cancel"

    try:
        session = s.checkout.Session.create(
            mode="subscription",
            allow_promotion_codes=True,
            line_items=[{"price": base_price, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {"url": session.get("url"), "id": session.get("id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"stripe_error:{type(e).__name__}")


@router.get("/price-ids")
async def price_ids():
    return _get_price_ids()


@router.get("/usage")
async def usage_snapshot():
    """Return a monthly per-tenant usage snapshot (requests), when available.

    This reads from the in-process TenantQuotaMiddleware counters; if unavailable,
    returns an empty structure. This endpoint is informational and not intended
    for strong billing—it serves operations visibility.
    """
    # Import here to avoid circulars
    try:
        from apps.gateway import api as gateway_api  # type: ignore
        app = gateway_api.app
        # Walk middlewares to find the quota middleware
        qmw = None
        # FastAPI wraps middlewares in starlette.middleware.errors.ServerErrorMiddleware
        # and starlette.middleware.exceptions.ExceptionMiddleware; access the internal stack
        cur = getattr(app, "user_middleware", [])
        # user_middleware is a list of Middleware objects; the actual instances are on app.middleware_stack
        stack = getattr(app, "middleware_stack", None)
        # Fallback: just call known attribute if present
        if hasattr(app, "middleware_stack") and hasattr(app.middleware_stack, "app"):
            node = app.middleware_stack
            # Traverse linked-list like structure to find our instance by class name
            seen = set()
            while hasattr(node, "app") and node not in seen:
                seen.add(node)
                inst = getattr(node, "app", None)
                if inst and inst.__class__.__name__ == "TenantQuotaMiddleware":
                    qmw = inst
                    break
                node = inst
        snap = getattr(qmw, "usage_snapshot", None) if qmw else None
        data = snap() if callable(snap) else {"month": None, "tenants": {}}
        return data
    except Exception:
        return {"month": None, "tenants": {}}
