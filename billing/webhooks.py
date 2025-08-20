from __future__ import annotations

import json
import os
from fastapi import APIRouter, HTTPException, Request

from billing.usage import GLOBAL_BILLING_REPO

try:
    import stripe  # type: ignore
except Exception:
    stripe = None  # type: ignore


router = APIRouter()


def _require_stripe() -> "stripe":
    if stripe is None:
        raise HTTPException(status_code=500, detail="stripe_not_installed")
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="missing_STRIPE_API_KEY")
    stripe.api_key = api_key
    return stripe


@router.post("/webhooks/stripe")
async def stripe_webhook(req: Request):
    s = _require_stripe()
    payload = await req.body()
    sig = req.headers.get("Stripe-Signature")
    wh_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    try:
        if wh_secret and sig:
            event = s.Webhook.construct_event(payload=payload, sig_header=sig, secret=wh_secret)
        else:
            event = json.loads(payload.decode("utf-8"))  # dev fallback
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_signature")

    t = event.get("type")
    data = event.get("data", {}).get("object", {})

    if t in ("customer.subscription.created", "customer.subscription.updated"):
        sub_id = data.get("id")
        items = data.get("items", {}).get("data", [])
        item_ids = [it.get("id") for it in items if it.get("id")]
        if sub_id and item_ids:
            GLOBAL_BILLING_REPO.upsert_subscription_items(sub_id, item_ids)

    elif t == "customer.subscription.deleted":
        sub_id = data.get("id")
        if sub_id:
            GLOBAL_BILLING_REPO.delete_subscription(sub_id)

    elif t in ("invoice.upcoming", "invoice.finalized"):
        # audit log hook (extend as needed)
        pass

    elif t == "invoice.payment_succeeded":
        # TODO: rotate monthly quota windows in app layer
        pass

    return {"ok": True}
