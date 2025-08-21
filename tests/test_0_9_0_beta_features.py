"""
Tests for 0.9.0-beta features: VAI, SBOM, and Merkle-Stream

Tests the implementation of:
- VAI (Verifiable Agent Identity) system with agent registry
- SBOM header processing and receipt enhancement
- Optional Merkle-Stream receipts for streaming data
"""
import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_vai_agent_registry_basic():
    """Test basic VAI agent registry operations."""
    # Use memory backend for testing
    with patch.dict(os.environ, {"VAI_BACKEND": "memory"}):
        from libs.odin_core.odin.agent_registry import AgentRegistry
        
        registry = AgentRegistry()
        
        # Register an agent
        agent = registry.register_agent(
            agent_id="test-agent-1",
            public_key="dGVzdC1wdWJsaWMta2V5",
            metadata={"name": "Test Agent", "version": "1.0.0"}
        )
        
        assert agent.agent_id == "test-agent-1"
        assert agent.status == "pending"
        assert agent.metadata["name"] == "Test Agent"
        
        # Get agent
        retrieved = registry.get_agent("test-agent-1")
        assert retrieved is not None
        assert retrieved.agent_id == "test-agent-1"
        
        # Approve agent
        success = registry.update_agent_status("test-agent-1", "approved", "admin-1")
        assert success
        
        # Validate approved agent
        validated = registry.validate_agent_header("test-agent-1")
        assert validated is not None
        assert validated.status == "approved"
        
        # Test rejected agent
        registry.register_agent("test-agent-2", "dGVzdC1wdWJsaWMta2V5Mg==")
        registry.update_agent_status("test-agent-2", "rejected")
        
        rejected = registry.validate_agent_header("test-agent-2")
        assert rejected is None


def test_vai_admin_endpoints():
    """Test VAI admin API endpoints."""
    with patch.dict(os.environ, {
        "VAI_BACKEND": "memory",
        "ODIN_ADMIN_KEY": "test-admin-key"
    }):
        from apps.gateway import api as gateway_api
        client = TestClient(gateway_api.app)
        
        headers = {"X-ODIN-Admin-Key": "test-admin-key"}
        
        # Register agent
        response = client.post(
            "/v1/admin/agents",
            json={
                "agent_id": "api-test-agent",
                "public_key": "dGVzdC1wdWJsaWMta2V5",
                "metadata": {"name": "API Test Agent"}
            },
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "api-test-agent"
        assert data["status"] == "pending"
        
        # List agents
        response = client.get("/v1/admin/agents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) >= 1
        
        # Get specific agent
        response = client.get("/v1/admin/agents/api-test-agent", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "api-test-agent"
        
        # Update agent status
        response = client.put(
            "/v1/admin/agents/api-test-agent/status",
            json={"status": "approved", "approved_by": "test-admin"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        
        # Health check
        response = client.get("/v1/admin/agents/_health", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["backend"] == "memory"


def test_sbom_header_processing():
    """Test SBOM header extraction and receipt enhancement."""
    from libs.odin_core.odin.sbom import extract_sbom_from_headers, enhance_receipt_with_sbom
    
    # Test SBOM header parsing
    headers = {
        "X-ODIN-Model": "gpt-4,claude-3",
        "X-ODIN-Tool": "search,calculator,weather",
        "X-ODIN-Prompt-CID": "bafybeiabc123,bafybeiabc456"
    }
    
    sbom = extract_sbom_from_headers(headers)
    assert len(sbom.models) == 2
    assert "gpt-4" in sbom.models
    assert "claude-3" in sbom.models
    
    assert len(sbom.tools) == 3
    assert "search" in sbom.tools
    assert "calculator" in sbom.tools
    assert "weather" in sbom.tools
    
    assert len(sbom.prompt_cids) == 2
    assert "bafybeiabc123" in sbom.prompt_cids
    
    # Test receipt enhancement
    receipt = {"payload": {"test": True}, "proof": {"oml_cid": "test-cid"}}
    enhanced = enhance_receipt_with_sbom(receipt, sbom)
    
    assert "sbom" in enhanced
    assert "models" in enhanced["sbom"]
    assert "tools" in enhanced["sbom"]
    assert "prompt_cids" in enhanced["sbom"]
    assert enhanced["sbom"]["models"] == ["gpt-4", "claude-3"]


def test_sbom_envelope_integration():
    """Test SBOM processing in envelope endpoint."""
    with patch.dict(os.environ, {"ODIN_STORAGE_BACKEND": "inmem"}):
        from apps.gateway import api as gateway_api
        client = TestClient(gateway_api.app)
        
        # Test envelope with SBOM headers
        headers = {
            "X-ODIN-Model": "gpt-4",
            "X-ODIN-Tool": "search",
            "X-ODIN-Prompt-CID": "bafybeiabc123"
        }
        
        response = client.post(
            "/v1/envelope",
            json={"test": "data", "intent": "echo"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify SBOM was added to receipt
        assert "sbom" in data
        assert "models" in data["sbom"]
        assert "tools" in data["sbom"]
        assert "prompt_cids" in data["sbom"]
        assert data["sbom"]["models"] == ["gpt-4"]
        assert data["sbom"]["tools"] == ["search"]
        assert data["sbom"]["prompt_cids"] == ["bafybeiabc123"]


def test_streaming_endpoints():
    """Test Merkle-Stream endpoints (when enabled)."""
    # Test the streaming components separately since full integration requires app reload
    from apps.gateway.streaming import is_streaming_enabled, get_stream_config
    
    # Test config functions work
    with patch.dict(os.environ, {"ODIN_STREAMING_ENABLED": "1"}):
        assert is_streaming_enabled() is True
        config = get_stream_config()
        assert config["enabled"] is True


def test_merkle_stream_processor():
    """Test Merkle stream processing logic."""
    from apps.gateway.streaming import MerkleStreamProcessor
    
    processor = MerkleStreamProcessor(chunk_size=2)
    
    # Add some chunks
    chunk1 = processor.add_chunk(0, {"data": [1, 2]})
    chunk2 = processor.add_chunk(1, {"data": [3, 4]})
    chunk3 = processor.add_chunk(2, {"data": [5]})
    
    assert len(processor.chunks) == 3
    assert chunk1.sequence == 0
    assert chunk2.sequence == 1
    assert chunk3.sequence == 2
    
    # Compute Merkle root
    merkle_root = processor.compute_merkle_root()
    assert isinstance(merkle_root, str)
    assert len(merkle_root) == 64  # SHA256 hex length
    
    # Generate receipt
    receipt = processor.generate_receipt("test-trace", "test-stream")
    assert receipt["type"] == "odin.stream.receipt"
    assert receipt["stream_id"] == "test-stream"
    assert receipt["trace_id"] == "test-trace"
    assert receipt["merkle_root"] == merkle_root
    assert receipt["chunk_count"] == 3


def test_vai_middleware_integration():
    """Test VAI middleware with agent validation."""
    # Test VAI components separately since full middleware integration requires app reload
    from libs.odin_core.odin.agent_registry import get_agent_registry
    from apps.gateway.middleware.vai import get_vai_agent_from_request
    
    with patch.dict(os.environ, {"VAI_BACKEND": "memory"}):
        registry = get_agent_registry()
        
        # Register and approve an agent
        registry.register_agent("approved-agent", "dGVzdC1wdWJsaWMta2V5")
        registry.update_agent_status("approved-agent", "approved", "admin")
        
        # Test validation works
        validated = registry.validate_agent_header("approved-agent")
        assert validated is not None
        assert validated.status == "approved"
        
        # Test rejection works
        rejected = registry.validate_agent_header("unknown-agent")
        assert rejected is None


def test_feature_flags():
    """Test that 0.9.0-beta features can be disabled via environment."""
    from libs.odin_core.odin.sbom import is_sbom_enabled
    from apps.gateway.streaming import is_streaming_enabled
    
    # Test SBOM enabled by default
    with patch.dict(os.environ, {}, clear=True):
        assert is_sbom_enabled() is True
    
    # Test SBOM can be disabled
    with patch.dict(os.environ, {"ODIN_SBOM_ENABLED": "0"}):
        assert is_sbom_enabled() is False
    
    # Test streaming disabled by default
    with patch.dict(os.environ, {}, clear=True):
        assert is_streaming_enabled() is False
    
    # Test streaming can be enabled
    with patch.dict(os.environ, {"ODIN_STREAMING_ENABLED": "1"}):
        assert is_streaming_enabled() is True


if __name__ == "__main__":
    # Run basic tests when executed directly
    print("Testing 0.9.0-beta features...")
    
    test_vai_agent_registry_basic()
    print("✓ VAI agent registry")
    
    test_sbom_header_processing()
    print("✓ SBOM header processing")
    
    test_merkle_stream_processor()
    print("✓ Merkle stream processor")
    
    test_feature_flags()
    print("✓ Feature flags")
    
    print("All basic tests passed!")
