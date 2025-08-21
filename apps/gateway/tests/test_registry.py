import json
from fastapi.testclient import TestClient
from libs.odin_core.odin.oml import to_oml_c, get_default_sft
from libs.odin_core.odin.ope import sign_over_content, OpeKeypair
from libs.odin_core.odin.envelope import ProofEnvelope
from libs.odin_core.odin.security.keystore import ensure_keystore_file
import os


def test_registry_register_and_fetch(monkeypatch):
    # In-memory backend for tests
    monkeypatch.setenv("ODIN_REGISTRY_BACKEND", "inmem")

    from apps.gateway import api as gateway_api
    c = TestClient(gateway_api.app)

    # 1) Build a signed envelope for an advertisement (avoid /v1/envelope to bypass enforcement)
    ad = {
        "intent": "odin.service.advertise",
        "service": "agent_beta",
        "version": "v1",
        "base_url": "http://127.0.0.1:9090",
        "endpoints": {"task": "/task"},
        "sft": ["beta@v1"],
        "labels": {"env": "test"},
        "ttl_s": 3600,
    }
    sft = get_default_sft()
    oml = to_oml_c(ad, sft=sft)
    # Load signer from keystore used by the app (tmp/odin/keystore.json by default)
    ks_path = os.environ.get("ODIN_KEYSTORE_PATH") or os.path.join(os.environ.get("ODIN_TMP_DIR", "tmp/odin"), "keystore.json")
    ks, active = ensure_keystore_file(ks_path)
    kp = ks[active] if active in ks else list(ks.values())[0] if ks else OpeKeypair.generate("k1")
    ope = sign_over_content(kp, oml, None)
    env = ProofEnvelope.from_ope(oml, ope, include_oml_c_b64=True)
    import json as _json
    envelope = _json.loads(env.to_json())

    # 2) Register using the signed advertisement
    reg_body = {"payload": ad, "proof": envelope}
    r = c.post("/v1/registry/register", json=reg_body)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert rid.startswith("svc_")

    # 3) List & filter
    ls = c.get("/v1/registry/services", params={"service": "agent_beta"})
    assert ls.status_code == 200
    data = ls.json()
    assert data["count"] >= 1
    ids = [i["id"] for i in data["items"]]
    assert rid in ids

    # 4) Get
    g = c.get(f"/v1/registry/services/{rid}")
    assert g.status_code == 200
    doc = g.json()
    assert doc["id"] == rid
    assert doc["payload"]["service"] == "agent_beta"
    assert "proof" in doc


def test_registry_discovery_has_endpoints():
    from apps.gateway import api as gateway_api
    c = TestClient(gateway_api.app)
    d = c.get("/.well-known/odin/discovery.json")
    assert d.status_code == 200
    j = d.json()
    eps = j["endpoints"]
    caps = j["capabilities"]
    assert "registry_register" in eps
    assert "registry_list" in eps
    assert "registry_get" in eps
    assert caps.get("registry") is True
