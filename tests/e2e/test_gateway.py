import pytest
from fastapi.testclient import TestClient
from apps.gateway.api import app
import os
import json
import yaml

client = TestClient(app)

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "odin_http_requests_total" in response.text

def test_envelope_endpoint():
    response = client.post("/v1/envelope", json={
        "payload": {
            "message": "hello"
        },
        "proof": {
            "type": "none"
        }
    })
    assert response.status_code == 200
    # The response is now a signed envelope, not a simple receipt
    assert "payload" in response.json()
    assert "proof" in response.json()

def test_business_to_banking_bridge():
    # This test requires the gateway to be running with the business realm pack
    # and the banking realm pack available for the bridge.
    # We will simulate this by placing a dummy SFT map and bridge config where they are expected.
    
    # Set up a test realm pack with permissive egress allowlist
    os.environ["ODIN_REALM_PACK_URI"] = "packs/realms/business-1.0.0/"
    
    # Reload the pack loader to pick up the new environment
    from apps.gateway.pack_loader import realm_pack_loader
    realm_pack_loader.reload()
    
    # Create bridge config
    bridges_dir = "configs/bridges"
    os.makedirs(bridges_dir, exist_ok=True)
    bridge_config = {
        "source_realm": "business",
        "target_realm": "banking",
        "sft_map": "business_to_banking.json"
    }
    bridge_config_path = os.path.join(bridges_dir, "business_to_banking.yaml")
    with open(bridge_config_path, "w") as f:
        yaml.dump(bridge_config, f)

    # Create SFT map
    sft_maps_dir = "config/sft_maps"
    os.makedirs(sft_maps_dir, exist_ok=True)
    
    sft_map = {
        "from_sft": "business",
        "to_sft": "banking",
        "intents": {
            "passthrough": {}
        }
    }
    sft_map_path = os.path.join(sft_maps_dir, "business_to_banking.json")
    with open(sft_map_path, "w") as f:
        json.dump(sft_map, f)

    response = client.post("/v1/bridge", 
        headers={
            "X-ODIN-Realm": "business",
            "X-ODIN-Target-Realm": "banking"
        },
        json={
            "payload": {
                "intent": "passthrough",
                "data": "some invoice data"
            },
            "from_sft": "business",
            "to_sft": "banking"
        }
    )
    
    assert response.status_code == 200
    
    # TODO: Verify receipts and hop chain
    
    os.remove(bridge_config_path)
    os.remove(sft_map_path)

