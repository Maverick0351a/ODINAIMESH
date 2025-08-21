import os, json, time, tempfile, pathlib
from odin.dynamic_reload import LocalStorage, DynamicAsset, DynamicReloader


def test_policy_reload_local():
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "policy.json"
        p.write_text(json.dumps({"allow": ["alpha.read"]}))
        storage = LocalStorage()
        asset = DynamicAsset("HEL", str(p), storage, ttl_secs=1)
        asset.maybe_reload(force=True)
        assert asset.value["allow"] == ["alpha.read"]
        # change file
        p.write_text(json.dumps({"allow": ["alpha.read", "beta.translate"]}))
        time.sleep(1.1)
        asset.maybe_reload()
        assert "beta.translate" in asset.value["allow"]


def test_reloader_maps_local():
    with tempfile.TemporaryDirectory() as td:
        reg = pathlib.Path(td) / "registry.json"
        reg.write_text(json.dumps({"sfts": ["alpha@v1","beta@v1"]}))
        maps_dir = pathlib.Path(td) / "maps"
        maps_dir.mkdir()
        (maps_dir / "alpha_to_beta.json").write_text(json.dumps({"map": "ok"}))
        os.environ["ODIN_STORAGE"] = "local"
        os.environ["ODIN_POLICY_URI"] = str(reg)  # just reuse file for simplicity
        os.environ["ODIN_SFT_REGISTRY_URI"] = str(reg)
        os.environ["ODIN_SFT_MAP_DIR"] = str(maps_dir)
        r = DynamicReloader(storage=LocalStorage(), policy_uri=str(reg),
                            sft_registry_uri=str(reg), sft_map_dir=str(maps_dir), ttl_secs=1)
        assert r.get_map("alpha_to_beta")["map"] == "ok"
