from __future__ import annotations

import json
import os
from pathlib import Path
from fastapi.testclient import TestClient


def _write_policy(path: Path, allow_delete: bool) -> None:
    policy = {
        "deny_intents": ["alpha.delete"] if not allow_delete else [],
        "allow_intents": ["alpha.request", "beta.request", "beta.reply", "alpha.result"],
        "require_reason": False,
    }
    path.write_text(json.dumps(policy, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _write_map_alpha_to_beta(path: Path) -> None:
    # Minimal map: alpha.request -> beta.request, identity fields
    m = {
        "from": "alpha@v1",
        "to": "beta@v1",
        "intents": {"alpha.request": "beta.request"},
        "fields": {"prompt": "prompt", "why": "why"},
    }
    path.write_text(json.dumps(m, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def test_admin_reload(monkeypatch, tmp_path):
    # Enable admin + token
    monkeypatch.setenv("ODIN_ENABLE_ADMIN", "1")
    monkeypatch.setenv("ODIN_ADMIN_TOKEN", "testtoken")

    # Point policy + maps to temp paths
    pol_path = tmp_path / "hel_policy.json"
    maps_dir = tmp_path / "maps"
    maps_dir.mkdir()

    _write_policy(pol_path, allow_delete=False)
    _write_map_alpha_to_beta(maps_dir / "alpha@v1__beta@v1.json")

    monkeypatch.setenv("ODIN_HEL_POLICY_PATH", str(pol_path))
    monkeypatch.setenv("ODIN_SFT_MAPS_DIR", str(maps_dir))

    # Import app after env is set
    from apps.gateway import api as gateway_api
    client = TestClient(gateway_api.app)

    # 1) Reload policy
    r1 = client.post("/v1/admin/reload/policy", headers={"X-Admin-Token": "testtoken"})
    assert r1.status_code == 200
    v1 = r1.json().get("policy_version")
    assert v1 is not None

    # 2) Reload maps
    r2 = client.post("/v1/admin/reload/maps", headers={"X-Admin-Token": "testtoken"})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["ok"] is True
    assert j2["count"] >= 1

    # 3) Verify translate uses newly loaded map
    body = {
        "payload": {"intent": "alpha.request", "prompt": "what is 2+2?", "why": "demo"},
        "from_sft": "alpha@v1",
        "to_sft": "beta@v1",
    }
    t = client.post("/v1/translate", json=body)
    assert t.status_code == 200, t.text

    data = t.json()
    # translate endpoint returns either a passthrough or an enveloped structure.
    # Normalize to the inner payload for assertion:
    payload = data.get("payload") if isinstance(data, dict) and "payload" in data else data
    assert isinstance(payload, dict)
    assert payload.get("intent") == "beta.request"

    # 4) Change policy content and reload again -> version must change
    _write_policy(pol_path, allow_delete=True)
    r3 = client.post("/v1/admin/reload/policy", headers={"X-Admin-Token": "testtoken"})
    assert r3.status_code == 200
    v2 = r3.json().get("policy_version")
    assert v2 is not None
    assert v2 != v1
