from __future__ import annotations

import math
import os
from typing import Optional

try:
    import stripe  # type: ignore
except Exception:
    stripe = None  # type: ignore


def _require_stripe() -> "stripe":
    if stripe is None:
        raise RuntimeError("stripe_not_installed")
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise RuntimeError("missing_STRIPE_API_KEY")
    stripe.api_key = api_key
    return stripe


def calc_overage_units(requests: int) -> int:
    """Round up to units of 1k requests."""
    if requests <= 0:
        return 0
    return math.ceil(requests / 1000)


def report_usage(subscription_item_id: str, requests: int, timestamp: Optional[int] = None):
    """Report metered usage in units of 1k requests using Stripe Usage Records.

    Returns the created stripe.UsageRecord.
    """
    s = _require_stripe()
    units = calc_overage_units(requests)
    if units <= 0:
        # nothing to report
        return None
    kwargs = {"subscription_item": subscription_item_id, "quantity": units, "action": "increment"}
    if timestamp is not None:
        kwargs["timestamp"] = timestamp
    return s.UsageRecord.create(**kwargs)  # type: ignore[arg-type]


# --- Repository abstraction (in-memory stub) --------------------------------
class BillingRepo:
    """Minimal in-memory repo mapping project_id -> overage subscription_item_id.

    Replace with Firestore/Postgres in production.
    """

    def __init__(self):
        self._project_overage_items: dict[str, str] = {}
        self._subscription_items_by_sub: dict[str, list[str]] = {}

    # Project linkage
    def set_project_overage_item(self, project_id: str, subscription_item_id: str):
        self._project_overage_items[project_id] = subscription_item_id

    def get_project_overage_item(self, project_id: str) -> Optional[str]:
        return self._project_overage_items.get(project_id)

    # Subscription lifecycle
    def upsert_subscription_items(self, subscription_id: str, item_ids: list[str]):
        self._subscription_items_by_sub[subscription_id] = item_ids

    def delete_subscription(self, subscription_id: str):
        self._subscription_items_by_sub.pop(subscription_id, None)


GLOBAL_BILLING_REPO = BillingRepo()


def record_request_event(project_id: str, count: int):
    """Lookup the overage subscription item for project and report usage."""
    item = GLOBAL_BILLING_REPO.get_project_overage_item(project_id)
    if not item:
        return None
    return report_usage(item, count)
