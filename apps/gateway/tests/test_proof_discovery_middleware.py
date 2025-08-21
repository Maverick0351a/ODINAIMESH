from fastapi.testclient import TestClient
from apps.gateway.api import app
from libs.odin_core.odin.constants import (
    X_ODIN_OPE,
    X_ODIN_JWKS,
    X_ODIN_PROOF_VERSION,
    ODIN_PROOF_VERSION_VALUE,
)


def test_discovery_headers_added(monkeypatch):
    c = TestClient(app)
    # Trigger a signed response via translate
    r = c.post("/v1/translate", json={"content": "hi", "target_lang": "en"})
    assert r.status_code == 200
    # Middleware should add discovery headers when X-ODIN-OPE present
    assert r.headers.get(X_ODIN_OPE)
    assert r.headers.get(X_ODIN_JWKS) == "/.well-known/odin/jwks.json"
    assert r.headers.get(X_ODIN_PROOF_VERSION) == ODIN_PROOF_VERSION_VALUE
