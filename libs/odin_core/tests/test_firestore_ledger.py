import os
import pytest

from libs.odin_core.odin.ledger import create_ledger_from_env


EMULATOR = os.getenv("FIRESTORE_EMULATOR_HOST")

pytestmark = pytest.mark.skipif(
    not EMULATOR, reason="Firestore emulator not running (FIRESTORE_EMULATOR_HOST unset)"
)


def test_firestore_ledger_roundtrip(monkeypatch):
    monkeypatch.setenv("ODIN_LEDGER_BACKEND", "firestore")
    # Emulator needs a project id
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "odin-local")

    # Optional: separate collection for tests
    monkeypatch.setenv("ODIN_FIRESTORE_COLLECTION", "odin_ledger_test")

    l = create_ledger_from_env()
    rec = {"route": "/v1/envelope", "kid": "testkid", "note": "roundtrip"}
    out = l.append(rec)
    assert out["kid"] == "testkid"
    assert isinstance(out["ts_ns"], int)
    items = l.list(limit=5)
    assert any(it.get("kid") == "testkid" for it in items)
