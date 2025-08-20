from __future__ import annotations

import builtins
import types
from billing.usage import calc_overage_units, report_usage


def test_calc_overage_units():
    assert calc_overage_units(1) == 1
    assert calc_overage_units(999) == 1
    assert calc_overage_units(1000) == 1
    assert calc_overage_units(1001) == 2


class DummyStripe:
    class UsageRecord:
        @staticmethod
        def create(**kwargs):
            return kwargs


def test_report_usage_monkeypatch(monkeypatch):
    # monkeypatch the stripe module inside billing.usage
    import billing.usage as usage

    dummy = DummyStripe()
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test")
    monkeypatch.setattr(usage, "stripe", dummy)
    # 2501 requests => 3 units
    r = report_usage("si_123", 2501)
    assert r["subscription_item"] == "si_123"
    assert r["quantity"] == 3
    assert r["action"] == "increment"
