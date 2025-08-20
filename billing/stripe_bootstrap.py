from __future__ import annotations

import os
from typing import Dict, Tuple

try:
    import stripe  # type: ignore
except Exception:
    stripe = None  # type: ignore


USD = "usd"


def _require_stripe() -> "stripe":
    if stripe is None:
        raise RuntimeError("stripe_not_installed")
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise RuntimeError("missing_STRIPE_API_KEY")
    stripe.api_key = api_key
    return stripe


def _find_product_by_name(s, name: str):
    res = s.Product.list(active=True, limit=100)
    for p in res.get("data", []):
        if p.get("name") == name:
            return p
    return None


def _find_price_by_lookup_key(s, lookup_key: str):
    res = s.Price.list(active=True, limit=100, lookup_keys=[lookup_key])
    data = res.get("data", [])
    return data[0] if data else None


def _ensure_product(s, name: str) -> str:
    existing = _find_product_by_name(s, name)
    if existing:
        return existing["id"]
    p = s.Product.create(name=name)
    return p["id"]


def _ensure_price(
    s,
    *,
    product: str,
    unit_amount: int,
    interval: str,
    usage_type: str,
    lookup_key: str,
    billing_scheme: str | None = None,
) -> str:
    # try by lookup_key first
    by_lookup = _find_price_by_lookup_key(s, lookup_key)
    if by_lookup:
        return by_lookup["id"]
    # fallback: search prices for product w/ same specs
    res = s.Price.list(product=product, active=True, limit=100)
    for pr in res.get("data", []):
        rec = pr.get("recurring") or {}
        if (
            pr.get("unit_amount") == unit_amount
            and pr.get("currency") == USD
            and rec.get("interval") == interval
            and rec.get("usage_type") == usage_type
            and (billing_scheme is None or pr.get("billing_scheme") == billing_scheme)
        ):
            # attach lookup_key for future lookups
            if not pr.get("lookup_key"):
                s.Price.modify(pr["id"], lookup_key=lookup_key)
            return pr["id"]
    # create new price
    kwargs = {
        "product": product,
        "unit_amount": unit_amount,
        "currency": USD,
        "recurring": {"interval": interval, "usage_type": usage_type},
        "lookup_key": lookup_key,
    }
    if billing_scheme:
        kwargs["billing_scheme"] = billing_scheme
    pr = s.Price.create(**kwargs)
    return pr["id"]


def bootstrap_stripe_products_and_prices() -> Dict[str, str]:
    """Create or reuse Stripe products/prices for ODIN tiers and return IDs.

    Returns a dict of env-var keys to IDs.
    """
    s = _require_stripe()

    # Products
    plugin_product_name = "ODIN Plugin Plans"
    enterprise_product_name = "ODIN Enterprise Services"
    plugin_product_id = _ensure_product(s, plugin_product_name)
    enterprise_product_id = _ensure_product(s, enterprise_product_name)

    # Prices
    ids: Dict[str, str] = {
        "STRIPE_PRODUCT_PLUGIN_PLANS": plugin_product_id,
        "STRIPE_PRODUCT_ENTERPRISE_PILOT": enterprise_product_id,
    }

    # Pro base $99/mo, licensed
    ids["STRIPE_PRICE_PRO_MONTHLY"] = _ensure_price(
        s,
        product=plugin_product_id,
        unit_amount=9900,
        interval="month",
        usage_type="licensed",
        lookup_key="odin_pro_monthly",
    )

    # Pro+ base $299/mo, licensed
    ids["STRIPE_PRICE_PRO_PLUS_MONTHLY"] = _ensure_price(
        s,
        product=plugin_product_id,
        unit_amount=29900,
        interval="month",
        usage_type="licensed",
        lookup_key="odin_pro_plus_monthly",
    )

    # Pro overage $0.50 per 1k_requests, metered
    ids["STRIPE_PRICE_PRO_OVERAGE_1K"] = _ensure_price(
        s,
        product=plugin_product_id,
        unit_amount=50,
        interval="month",
        usage_type="metered",
        billing_scheme="per_unit",
        lookup_key="odin_pro_overage_1k",
    )

    # Pro+ overage $0.25 per 1k_requests, metered
    ids["STRIPE_PRICE_PRO_PLUS_OVERAGE_1K"] = _ensure_price(
        s,
        product=plugin_product_id,
        unit_amount=25,
        interval="month",
        usage_type="metered",
        billing_scheme="per_unit",
        lookup_key="odin_pro_plus_overage_1k",
    )

    # Enterprise Pilot: 6-month recurring $50,000
    ids["STRIPE_PRICE_ENTERPRISE_PILOT_6MO"] = _ensure_price(
        s,
        product=enterprise_product_id,
        unit_amount=5000000,
        interval="month",  # Stripe doesn't support 6mo directly; model as every 6 months via interval_count
        usage_type="licensed",
        lookup_key="odin_enterprise_pilot_6mo",
    )
    # ensure interval_count=6
    s.Price.modify(ids["STRIPE_PRICE_ENTERPRISE_PILOT_6MO"], recurring={"interval": "month", "interval_count": 6, "usage_type": "licensed"})

    # Pretty print summary
    print("\nStripe IDs (created or reused):")
    for k, v in ids.items():
        print(f"  {k}: {v}")

    return ids
