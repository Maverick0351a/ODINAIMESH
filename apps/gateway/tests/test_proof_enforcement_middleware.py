from __future__ import annotations

import base64
import json
from fastapi.testclient import TestClient
import os
import importlib

import apps.gateway.api as api
import json
from pathlib import Path


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def test_enforcement_blocks_missing_proof_and_passes_when_present(monkeypatch, tmp_path):
    # Ensure no policy leakage from other tests
    monkeypatch.delenv("ODIN_HEL_POLICY_PATH", raising=False)
    # Enable middleware for /v1/envelope route strictly
    monkeypatch.setenv("ODIN_ENFORCE_ROUTES", "/v1/envelope")
    monkeypatch.setenv("ODIN_ENFORCE_REQUIRE", "1")
    # Reload app module so middleware reads env at import time
    importlib.reload(api)
    client = TestClient(api.app)

    # Missing proof -> 401
    r1 = client.post("/v1/envelope", json={"foo": "bar"})
    assert r1.status_code == 401
    j1 = r1.json()
    assert j1["error"] == "odin.proof.missing"

    # Switch enforcement away from /v1/envelope to fetch an example envelope
    monkeypatch.setenv("ODIN_ENFORCE_ROUTES", "/v1/echo")
    importlib.reload(api)
    client2 = TestClient(api.app)
    payload = {"foo": "bar"}
    r3 = client2.post("/v1/envelope", json={"payload": payload})
    assert r3.status_code == 200
    env = r3.json()["proof"]
    # Inline JWKS to avoid external fetch during tests
    rjwks = client2.get("/.well-known/odin/jwks.json")
    assert rjwks.status_code == 200
    jwks = rjwks.json()
    env["jwks_inline"] = jwks
    env.pop("jwks_url", None)

    # Now enforce again on /v1/envelope and ensure passing with proof
    monkeypatch.setenv("ODIN_ENFORCE_ROUTES", "/v1/envelope")
    importlib.reload(api)
    client3 = TestClient(api.app)
    r4 = client3.post("/v1/envelope", json={"payload": {"hello": "world"}, "proof": env})
    assert r4.status_code == 200
    # Success indicates middleware accepted proof; response body shape is route-defined

def test_enforcement_policy_blocked_kid_403(tmp_path):
    # First, run with enforcement off for /v1/envelope to get a valid envelope
    os.environ["ODIN_ENFORCE_ROUTES"] = "/v1/echo"
    os.environ["ODIN_ENFORCE_REQUIRE"] = "1"
    importlib.reload(api)
    client = TestClient(api.app)
    payload = {"foo": "bar"}
    r = client.post("/v1/envelope", json={"payload": payload})
    assert r.status_code == 200
    env = r.json()["proof"]
    # Inline JWKS to avoid fetch
    rjwks = client.get("/.well-known/odin/jwks.json")
    env["jwks_inline"] = rjwks.json()
    env.pop("jwks_url", None)

    # Prepare blocking policy
    pol = {"allow_kids": ["*"], "deny_kids": ["*"], "allowed_jwks_hosts": ["*"]}
    p = Path(tmp_path) / "policy.json"
    p.write_text(json.dumps(pol), encoding="utf-8")

    # Now enforce on /v1/envelope with policy
    os.environ["ODIN_ENFORCE_ROUTES"] = "/v1/envelope"
    os.environ["ODIN_HEL_POLICY_PATH"] = str(p)
    importlib.reload(api)
    client2 = TestClient(api.app)
    r2 = client2.post("/v1/envelope", json={"payload": payload, "proof": env})
    assert r2.status_code == 403
    assert r2.json().get("error") == "odin.policy.blocked"


def test_unenforced_route_passes_without_proof():
    # Ensure no policy leakage from other tests
    os.environ.pop("ODIN_HEL_POLICY_PATH", None)
    # Enforce only on /v1/envelope
    os.environ["ODIN_ENFORCE_ROUTES"] = "/v1/envelope"
    os.environ["ODIN_ENFORCE_REQUIRE"] = "1"
    importlib.reload(api)
    client = TestClient(api.app)
    # Call open echo route without proof
    r = client.post("/v1/echo", json={"message": "hi"})
    # Echo route expects model; should succeed with 200
    assert r.status_code == 200
    assert r.json().get("echo") == "hi"

