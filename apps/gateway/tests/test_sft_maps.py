import json
from pathlib import Path

from fastapi.testclient import TestClient
from apps.gateway.api import app

client = TestClient(app)


def test_list_and_get_maps(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ODIN_SFT_MAPS_DIR", str(tmp_path))

    # two valid maps
    m1 = {"from_sft": "test/A@1", "to_sft": "test/B@1", "fields": {"user_name": "name"}}
    m2 = {"from_sft": "alpha@1", "to_sft": "beta@2", "intents": {"greet": "say_hello"}, "const": {"v": 1}}

    (tmp_path / "test_A@1__test_B@1.json").write_text(json.dumps(m1), encoding="utf-8")
    (tmp_path / "alpha@1__beta@2.json").write_text(json.dumps(m2), encoding="utf-8")

    # one invalid JSON that should be ignored in listing
    (tmp_path / "broken.json").write_text("{ not: json }", encoding="utf-8")

    r = client.get("/v1/sft/maps")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    names = {m["name"] for m in body["maps"]}
    assert {"test_A@1__test_B@1.json", "alpha@1__beta@2.json"} <= names

    # Ensure sha256 surfaced
    digests = [m.get("sha256") for m in body["maps"]]
    assert all(isinstance(d, str) and len(d) == 64 for d in digests)

    # fetch a specific map
    r = client.get("/v1/sft/maps/test_A@1__test_B@1.json")
    assert r.status_code == 200
    assert r.json()["fields"]["user_name"] == "name"
    # ETag present for caching
    assert r.headers.get("ETag", "").startswith('W/"')


def test_map_get_guardrails(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ODIN_SFT_MAPS_DIR", str(tmp_path))

    # invalid name -> 400 (contains path separator)
    r = client.get("/v1/sft/maps/bad/evil.json")
    assert r.status_code == 400
    d = r.json()
    assert d["detail"]["error"] == "odin.sft_map.bad_name"

    # not found -> 404
    r = client.get("/v1/sft/maps/does_not_exist.json")
    assert r.status_code == 404

    # invalid json -> 422
    (tmp_path / "bad.json").write_text("{ nope", encoding="utf-8")
    r = client.get("/v1/sft/maps/bad.json")
    assert r.status_code == 422
    d = r.json()
    assert d["detail"]["error"] == "odin.sft_map.invalid_json"
