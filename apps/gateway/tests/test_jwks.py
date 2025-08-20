from fastapi.testclient import TestClient
from apps.gateway.api import app
import base64


def test_jwks_from_keystore(tmp_path, monkeypatch):
    # Ensure persistent keystore exists
    ks_path = tmp_path / "keystore.json"
    monkeypatch.setenv("ODIN_KEYSTORE_PATH", str(ks_path))
    c = TestClient(app)
    r = c.get("/.well-known/odin/jwks.json")
    assert r.status_code == 200
    data = r.json()
    assert "keys" in data and isinstance(data["keys"], list) and len(data["keys"]) >= 1
    jwk = data["keys"][0]
    assert jwk.get("kty") == "OKP" and jwk.get("crv") == "Ed25519" and "x" in jwk


def test_jwks_single_pubkey_env(monkeypatch):
    # Provide a known 32-byte value as base64
    raw = b"\x01" * 32
    b64u = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    monkeypatch.setenv("ODIN_OPE_PUBKEY", b64u)
    monkeypatch.setenv("ODIN_OPE_KID", "envk")
    c = TestClient(app)
    r = c.get("/.well-known/odin/jwks.json")
    assert r.status_code == 200
    data = r.json()
    assert data.get("active_kid") == "envk"
    assert data["keys"][0]["x"] == b64u
