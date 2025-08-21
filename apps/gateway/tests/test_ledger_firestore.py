import os
import pytest

from libs.odin_core.odin.ledger import create_ledger_from_env

EMULATOR = os.getenv("FIRESTORE_EMULATOR_HOST")
pytestmark = pytest.mark.skipif(
    not EMULATOR, reason="Firestore emulator not running (FIRESTORE_EMULATOR_HOST unset)"
)


def test_gateway_firestore_ledger_roundtrip(monkeypatch):
    # Select Firestore backend
    monkeypatch.setenv("ODIN_LEDGER_BACKEND", "firestore")
    # Emulator requires a project
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "odin-local")
    # Separate test collection
    monkeypatch.setenv("ODIN_FIRESTORE_COLLECTION", "odin_ledger_test_gw")

    ledger = create_ledger_from_env()
    rec = {"route": "/v1/ledger/append", "source": "gw", "kid": "gwkid"}
    saved = ledger.append(rec)
    assert saved["kid"] == "gwkid"
    assert isinstance(saved["ts_ns"], int)

    # Ensure we can list and find the record
    items = ledger.list(limit=10)
    assert any(it.get("kid") == "gwkid" and it.get("source") == "gw" for it in items)
