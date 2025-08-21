"""
Integration test for SFT Quick Wins in the gateway bridge.

Tests end-to-end functionality of:
1. Canonicalization contract for reproducible CIDs
2. Field-level provenance tracking in translation receipts
3. Coverage percentage and required-field gates
4. Deterministic defaults and enum validation
5. SFT type headers (X-ODIN-SFT-Input-Type, X-ODIN-SFT-Desired-Type)
"""
import pytest
import json
import asyncio
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from fastapi import Request

# Import the FastAPI app for testing
from apps.gateway.api import app as gateway_app


class TestSFTQuickWinsIntegration:
    """Integration tests for SFT Quick Wins in the gateway bridge."""
    
    def setup_method(self):
        """Set up test client and common test data."""
        self.client = TestClient(gateway_app)
        
        # Sample payload for testing
        self.test_payload = {
            "agent_id": "test-agent-123",
            "query": "What is the weather today?",
            "context": "User wants weather information",
            "internal_metadata": "should_be_dropped",
            "debug_flags": ["verbose", "trace"]
        }
        
        # Expected enhanced SFT map for testing
        self.enhanced_map_data = {
            "from_sft": "odin.agent_request@v1",
            "to_sft": "openai.tool_call@v1",
            "fields": {
                "agent_id": "tool_id",
                "query": "prompt",
                "context": "system_message"
            },
            "const": {
                "model": "gpt-4",
                "api_version": "2024-12-01"
            },
            "drop": [
                "internal_metadata",
                "debug_flags"
            ],
            "defaults": {
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            },
            "enum_constraints": {
                "model": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
            },
            "required_fields": [
                "tool_id",
                "prompt"
            ],
            "canon_alg": "json/nfc/no_ws/sort_keys"
        }
    
    @patch('libs.odin_core.odin.translate.validate_obj')
    @patch('libs.odin_core.odin.translate.load_map_from_path')
    @patch('apps.gateway.security.http_signature.require_http_signature')
    @patch('apps.gateway.security.id_token.maybe_get_id_token')
    def test_bridge_with_sft_headers(self, mock_id_token, mock_http_sig, mock_load_map, mock_validate):
        """Test bridge endpoint with SFT type headers (Quick Win 5)."""
        # Mock authentication and validation
        mock_http_sig.return_value = None
        mock_id_token.return_value = ("test-user", {})
        mock_validate.return_value = []  # Valid payload
        
        # Mock enhanced map loading
        from libs.odin_core.odin.translate import EnhancedSftMap
        enhanced_map = EnhancedSftMap(**self.enhanced_map_data)
        mock_load_map.return_value = enhanced_map
        
        # Headers with SFT type declarations
        headers = {
            "X-ODIN-SFT-Input-Type": "odin.agent_request@v1",
            "X-ODIN-SFT-Desired-Type": "openai.tool_call@v1",
            "X-ODIN-SFT-Canon-Alg": "json/nfc/no_ws/sort_keys",
            "Content-Type": "application/json"
        }
        
        # Make request to bridge endpoint
        response = self.client.post(
            "/v1/bridge/transform",
            json=self.test_payload,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify transformation
        assert "payload" in data
        transformed = data["payload"]
        assert transformed["tool_id"] == "test-agent-123"  # agent_id -> tool_id
        assert transformed["prompt"] == "What is the weather today?"  # query -> prompt
        assert transformed["model"] == "gpt-4"  # const overlay
        assert transformed["temperature"] == 0.7  # default applied
        assert "internal_metadata" not in transformed  # dropped
        
        # Verify SFT metadata
        assert "sft" in data
        assert data["sft"]["from"] == "odin.agent_request@v1"
        assert data["sft"]["to"] == "openai.tool_call@v1"
        
        # Verify translation receipt (Quick Win 2)
        if "translation_receipt" in data:
            receipt = data["translation_receipt"]
            assert "field_provenance" in receipt
            assert "coverage_percent" in receipt
            assert receipt["canon_alg"] == "json/nfc/no_ws/sort_keys"
        
        # Verify canonicalization headers (Quick Win 1)
        assert "X-ODIN-SFT-Canon-CID-Input" in response.headers
        assert "X-ODIN-SFT-Canon-CID-Output" in response.headers
        assert response.headers["X-ODIN-SFT-Canon-Algorithm"] == "json/nfc/no_ws/sort_keys"
    
    @patch('libs.odin_core.odin.translate.validate_obj')
    @patch('libs.odin_core.odin.translate.get_coverage_requirements')
    @patch('apps.gateway.security.http_signature.require_http_signature')
    @patch('apps.gateway.security.id_token.maybe_get_id_token')
    def test_bridge_coverage_gates(self, mock_id_token, mock_http_sig, mock_coverage_reqs, mock_validate):
        """Test coverage gate enforcement (Quick Win 3)."""
        # Mock authentication
        mock_http_sig.return_value = None
        mock_id_token.return_value = ("test-user", {})
        mock_validate.return_value = []  # Valid payload
        
        # Mock coverage requirements to enforce gates
        mock_coverage_reqs.return_value = {
            "min_coverage_percent": 90.0,  # High threshold
            "required_fields": ["tool_id", "prompt"],
            "enforce_gates": True
        }
        
        # Payload that will have low coverage due to many dropped fields
        low_coverage_payload = {
            "agent_id": "test",
            "query": "test",
            "field1": "drop1",
            "field2": "drop2", 
            "field3": "drop3",
            "field4": "drop4",
            "field5": "drop5"
        }
        
        with patch('apps.gateway.bridge._load_sft_map') as mock_load_map:
            from libs.odin_core.odin.translate import EnhancedSftMap
            enhanced_map = EnhancedSftMap(
                from_sft="test@v1",
                to_sft="test@v2",
                fields={"agent_id": "tool_id", "query": "prompt"},
                drop=["field1", "field2", "field3", "field4", "field5"]  # Drop most fields
            )
            mock_load_map.return_value = enhanced_map
            
            response = self.client.post(
                "/v1/bridge/transform",
                json=low_coverage_payload,
                params={"from_sft": "test@v1", "to_sft": "test@v2"}
            )
            
            # Should fail due to insufficient coverage
            assert response.status_code == 422
            error_data = response.json()
            assert "insufficient_coverage" in error_data["detail"]["error"]
    
    @patch('libs.odin_core.odin.translate.validate_obj')
    @patch('apps.gateway.security.http_signature.require_http_signature')
    @patch('apps.gateway.security.id_token.maybe_get_id_token')
    def test_bridge_enum_constraint_validation(self, mock_id_token, mock_http_sig, mock_validate):
        """Test enum constraint validation (Quick Win 4)."""
        # Mock authentication
        mock_http_sig.return_value = None
        mock_id_token.return_value = ("test-user", {})
        mock_validate.return_value = []
        
        # Create a map with enum constraints that will be violated
        with patch('apps.gateway.bridge._load_sft_map') as mock_load_map:
            from libs.odin_core.odin.translate import EnhancedSftMap
            enhanced_map = EnhancedSftMap(
                from_sft="test@v1",
                to_sft="test@v2",
                const={"model": "invalid-model"},  # Will violate enum constraint
                enum_constraints={
                    "model": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
                }
            )
            mock_load_map.return_value = enhanced_map
            
            response = self.client.post(
                "/v1/bridge/transform",
                json={"test": "data"},
                params={"from_sft": "test@v1", "to_sft": "test@v2"}
            )
            
            # Should fail due to enum constraint violation
            assert response.status_code == 422
            error_data = response.json()
            assert "enum_violation" in error_data["detail"]["error"]
    
    def test_canonicalization_reproducibility(self):
        """Test that canonicalization produces reproducible results (Quick Win 1)."""
        from libs.odin_core.odin.translate import canonicalize_json, compute_canonical_cid
        
        # Test objects with different field ordering
        obj1 = {"b": 2, "a": 1, "c": {"z": 26, "y": 25}}
        obj2 = {"c": {"y": 25, "z": 26}, "a": 1, "b": 2}
        
        # Should produce identical canonical JSON
        canon1 = canonicalize_json(obj1)
        canon2 = canonicalize_json(obj2)
        assert canon1 == canon2
        
        # Should produce identical CIDs
        cid1 = compute_canonical_cid(obj1)
        cid2 = compute_canonical_cid(obj2)
        assert cid1 == cid2
        assert cid1.startswith("b")  # base32 multibase prefix
    
    def test_field_provenance_tracking(self):
        """Test field-level provenance tracking (Quick Win 2)."""
        from libs.odin_core.odin.translate import (
            EnhancedSftMap, translate, FieldProvenance
        )
        
        # Create enhanced map with various operations
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            fields={"old_name": "new_name"},
            const={"version": "2.0"},
            drop=["temp_field"],
            defaults={"status": "active"}
        )
        
        payload = {
            "old_name": "test_value",
            "temp_field": "remove_me",
            "keep_field": "unchanged"
        }
        
        with patch('libs.odin_core.odin.translate.validate_obj', return_value=[]):
            result, receipt = translate(payload, enhanced_map, generate_receipt=True)
            
            # Verify provenance tracking
            provenance = receipt.field_provenance
            operations = {fp.operation for fp in provenance}
            
            assert "rename" in operations  # old_name -> new_name
            assert "const" in operations   # version constant
            assert "drop" in operations    # temp_field dropped
            assert "default" in operations # status default
            assert "passthrough" in operations # keep_field unchanged
            
            # Verify specific field transformations
            rename_op = next(fp for fp in provenance if fp.operation == "rename")
            assert rename_op.source_field == "old_name"
            assert rename_op.target_field == "new_name"
            assert rename_op.source_value == "test_value"
    
    def test_deterministic_defaults_application(self):
        """Test deterministic defaults application (Quick Win 4)."""
        from libs.odin_core.odin.translate import EnhancedSftMap
        
        enhanced_map = EnhancedSftMap(
            from_sft="test@v1",
            to_sft="test@v2",
            defaults={
                "status": "pending",
                "priority": 1,
                "enabled": True
            }
        )
        
        # Test with partial data
        obj1 = {"name": "test", "status": None}
        result1 = enhanced_map.apply_defaults(obj1)
        
        assert result1["name"] == "test"
        assert result1["status"] == "pending"  # Applied default
        assert result1["priority"] == 1       # Applied default
        assert result1["enabled"] is True     # Applied default
        
        # Test with existing data (should not override)
        obj2 = {"name": "test", "status": "active", "priority": 5}
        result2 = enhanced_map.apply_defaults(obj2)
        
        assert result2["status"] == "active"  # Existing value preserved
        assert result2["priority"] == 5      # Existing value preserved
        assert result2["enabled"] is True    # Default applied for missing field


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
