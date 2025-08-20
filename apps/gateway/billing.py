from __future__ import annotations

import os
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

try:
    import stripe  # type: ignore
except Exception as _e:  # pragma: no cover - optional in test envs
    stripe = None  # type: ignore


router = APIRouter(prefix="/v1/billing", tags=["billing"])


class CreateCheckoutSessionIn(BaseModel):
    # Price ID from Stripe dashboard (e.g., price_...)
    price: str
    # Number of seats or quantity, default 1
    quantity: int | None = 1
    # Return URLs
    success_url: str
    cancel_url: str
    # Optional customer email to prefill
    customer_email: str | None = None
    # Metadata to attach to the Checkout Session
    metadata: dict[str, str] | None = None


def _require_stripe() -> "stripe":
    if stripe is None:
        raise HTTPException(status_code=500, detail="stripe_not_installed")
    sk = os.getenv("STRIPE_SECRET_KEY")
    if not sk:
        raise HTTPException(status_code=500, detail="missing_STRIPE_SECRET_KEY")
    stripe.api_key = sk
    return stripe


@router.post("/checkout/sessions")
async def create_checkout_session(body: CreateCheckoutSessionIn):
    s = _require_stripe()
    try:
        session = s.checkout.Session.create(
            mode="payment",  # change to subscription if recurring
            line_items=[
                {
                    "price": body.price,
                    "quantity": body.quantity or 1,
                }
            ],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            customer_email=body.customer_email,
            metadata=body.metadata or {},
            automatic_tax={"enabled": True},
        )
        return {"id": session["id"], "url": session.get("url")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"stripe_error:{type(e).__name__}")


@router.post("/webhooks/stripe")
async def stripe_webhook(req: Request):
    # Verify via endpoint secret when set
    payload = await req.body()
    sig_header = req.headers.get("Stripe-Signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    s = _require_stripe()
    event = None
    try:
        if endpoint_secret and sig_header:
            event = s.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=endpoint_secret)
        else:
            # Unsafe fallback for local dev only
            event = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid_webhook_signature")

    t = (event or {}).get("type")
    data = (event or {}).get("data", {}).get("object", {})
    # Minimal handling examples; extend as needed
    if t == "checkout.session.completed":
        # TODO: mark order as paid, provision access, etc.
        pass
    elif t == "invoice.paid":
        pass
    elif t == "invoice.payment_failed":
        pass

    return {"received": True}
