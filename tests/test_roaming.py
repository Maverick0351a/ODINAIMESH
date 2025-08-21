"""
Test Suite for ODIN Roaming Pass System

Tests AI-to-AI roaming functionality including pass generation,
verification, HEL integration, and receipt tracking.
"""
import pytest
import json
import time
import tempfile
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from odin.roaming import (
    RoamingPassGenerator, RoamingPassVerifier, RoamingConfig, TrustAnchor,
    generate_ed25519_keypair, load_roaming_config, create_roaming_receipt_block,
    roaming_valid, roaming_scope_contains
)
from gateway.routers.roaming import router as roaming_router
from gateway.middleware.roaming import RoamingMiddleware, get_roaming_claims


class TestRoamingPassGeneration:
    """Test roaming pass generation (Home Gateway)."""
    
    def setup_method(self):
        """Set up test components."""
        self.private_key, self.public_key = generate_ed25519_keypair()
        self.generator = RoamingPassGenerator(
            gateway_base_url="https://home-gw.example.com",
            private_key=self.private_key,
            kid="test-key-2025"
        )
    
    def test_mint_basic_pass(self):
        """Test basic roaming pass generation."""
        pass_token, metadata = self.generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post", "translate:read"],
            ttl_seconds=300
        )
        
        # Verify token format
        assert isinstance(pass_token, str)
        assert len(pass_token.split('.')) == 3  # header.payload.signature
        
        # Verify metadata
        assert "exp" in metadata
        assert "jti" in metadata
        assert metadata["scope"] == ["mesh:post", "translate:read"]
        assert metadata["realm_dst"] == "banking"
    
    def test_mint_pass_with_binding(self):
        """Test pass generation with PoP binding."""
        bind_config = {"method": "OPE", "hash_alg": "sha256"}
        
        pass_token, metadata = self.generator.mint_pass(
            agent_did="did:odin:agent-456",
            audience="https://visited-gw.example.com",
            realm_dst="fintech",
            scope=["bridge:post"],
            ttl_seconds=600,
            bind=bind_config
        )
        
        # Decode and verify binding is included
        parts = pass_token.split('.')
        payload_json = json.loads(
            self._decode_b64url(parts[1])
        )
        
        assert "bind" in payload_json
        assert payload_json["bind"] == bind_config
    
    def test_pass_expiration_timing(self):
        """Test pass expiration timing."""
        ttl = 120
        start_time = int(time.time())
        
        pass_token, metadata = self.generator.mint_pass(
            agent_did="did:odin:agent-789",
            audience="https://visited-gw.example.com",
            realm_dst="retail",
            scope=["mesh:post"],
            ttl_seconds=ttl
        )
        
        # Decode payload to check timing
        parts = pass_token.split('.')
        payload = json.loads(self._decode_b64url(parts[1]))
        
        assert payload["nbf"] >= start_time
        assert payload["exp"] == payload["nbf"] + ttl
        assert payload["exp"] <= start_time + ttl + 2  # Allow 2 second variance
    
    def _decode_b64url(self, data: str) -> str:
        """Helper to decode base64url."""
        import base64
        padding = '=' * (4 - len(data) % 4) if len(data) % 4 else ''
        return base64.urlsafe_b64decode(data + padding).decode()


class TestRoamingPassVerification:
    """Test roaming pass verification (Visited Gateway)."""
    
    def setup_method(self):
        """Set up test components."""
        self.private_key, self.public_key = generate_ed25519_keypair()
        self.generator = RoamingPassGenerator(
            gateway_base_url="https://home-gw.example.com",
            private_key=self.private_key,
            kid="test-key-2025"
        )
        
        # Create trust anchor config
        trust_anchor = TrustAnchor(
            name="test-home",
            iss="https://home-gw.example.com",
            discovery="https://home-gw.example.com/.well-known/odin/discovery.json",
            realms_allowed=["business", "banking", "fintech"],
            audience_allowed=["https://visited-gw.example.com"],
            max_ttl_seconds=600
        )
        
        config = RoamingConfig(version=1, issuers=[trust_anchor])
        self.verifier = RoamingPassVerifier(config, "https://visited-gw.example.com")
    
    def test_verify_valid_pass(self):
        """Test verification of valid roaming pass."""
        # Generate pass
        pass_token, _ = self.generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post", "translate:read"],
            ttl_seconds=300
        )
        
        # Mock JWKS fetch
        with patch.object(self.verifier, '_get_public_key', return_value=self.public_key):
            valid, claims, error = self.verifier.verify_pass(
                roaming_pass=pass_token,
                agent_did="did:odin:agent-123",
                target_realm="banking",
                requested_operation="mesh:post"
            )
        
        assert valid is True
        assert error is None
        assert claims["sub"] == "did:odin:agent-123"
        assert claims["realm_dst"] == "banking"
        assert "mesh:post" in claims["scope"]
    
    def test_verify_expired_pass(self):
        """Test verification of expired pass."""
        # Generate pass with short TTL
        pass_token, _ = self.generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post"],
            ttl_seconds=1
        )
        
        # Wait for expiration
        time.sleep(2)
        
        with patch.object(self.verifier, '_get_public_key', return_value=self.public_key):
            valid, claims, error = self.verifier.verify_pass(
                roaming_pass=pass_token,
                agent_did="did:odin:agent-123",
                target_realm="banking",
                requested_operation="mesh:post"
            )
        
        assert valid is False
        assert error == "expired"
    
    def test_verify_agent_mismatch(self):
        """Test verification with agent mismatch."""
        pass_token, _ = self.generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post"],
            ttl_seconds=300
        )
        
        with patch.object(self.verifier, '_get_public_key', return_value=self.public_key):
            valid, claims, error = self.verifier.verify_pass(
                roaming_pass=pass_token,
                agent_did="did:odin:agent-456",  # Different agent
                target_realm="banking",
                requested_operation="mesh:post"
            )
        
        assert valid is False
        assert error == "agent_mismatch"
    
    def test_verify_realm_mismatch(self):
        """Test verification with realm mismatch."""
        pass_token, _ = self.generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post"],
            ttl_seconds=300
        )
        
        with patch.object(self.verifier, '_get_public_key', return_value=self.public_key):
            valid, claims, error = self.verifier.verify_pass(
                roaming_pass=pass_token,
                agent_did="did:odin:agent-123",
                target_realm="fintech",  # Different realm
                requested_operation="mesh:post"
            )
        
        assert valid is False
        assert error == "realm_mismatch"
    
    def test_verify_scope_mismatch(self):
        """Test verification with insufficient scope."""
        pass_token, _ = self.generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["translate:read"],  # Only read access
            ttl_seconds=300
        )
        
        with patch.object(self.verifier, '_get_public_key', return_value=self.public_key):
            valid, claims, error = self.verifier.verify_pass(
                roaming_pass=pass_token,
                agent_did="did:odin:agent-123",
                target_realm="banking",
                requested_operation="mesh:post"  # Requires post access
            )
        
        assert valid is False
        assert error == "scope_mismatch"
    
    def test_verify_issuer_not_trusted(self):
        """Test verification with untrusted issuer."""
        # Create generator with different issuer
        other_private_key, _ = generate_ed25519_keypair()
        other_generator = RoamingPassGenerator(
            gateway_base_url="https://untrusted-gw.example.com",
            private_key=other_private_key,
            kid="untrusted-key"
        )
        
        pass_token, _ = other_generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post"],
            ttl_seconds=300
        )
        
        valid, claims, error = self.verifier.verify_pass(
            roaming_pass=pass_token,
            agent_did="did:odin:agent-123",
            target_realm="banking",
            requested_operation="mesh:post"
        )
        
        assert valid is False
        assert error == "issuer_not_trusted"


class TestRoamingConfig:
    """Test roaming configuration loading."""
    
    def test_load_config_from_file(self):
        """Test loading roaming config from YAML file."""
        config_data = {
            "version": 1,
            "issuers": [
                {
                    "name": "test-issuer",
                    "iss": "https://test.example.com",
                    "discovery": "https://test.example.com/.well-known/odin/discovery.json",
                    "realms_allowed": ["test"],
                    "audience_allowed": ["https://visited.example.com"],
                    "max_ttl_seconds": 300
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = load_roaming_config(config_path)
            
            assert config.version == 1
            assert len(config.issuers) == 1
            
            issuer = config.issuers[0]
            assert issuer.name == "test-issuer"
            assert issuer.iss == "https://test.example.com"
            assert issuer.realms_allowed == ["test"]
            assert issuer.max_ttl_seconds == 300
            
        finally:
            os.unlink(config_path)
    
    def test_config_validation(self):
        """Test configuration validation."""
        trust_anchor = TrustAnchor(
            name="test",
            iss="https://test.example.com",
            discovery="https://test.example.com/.well-known/odin/discovery.json",
            realms_allowed=["business"],
            audience_allowed=["https://visited.example.com"],
            max_ttl_seconds=600
        )
        
        config = RoamingConfig(version=1, issuers=[trust_anchor])
        
        assert config.version == 1
        assert len(config.issuers) == 1
        assert config.issuers[0].name == "test"


class TestRoamingAPI:
    """Test roaming API endpoints."""
    
    def setup_method(self):
        """Set up test FastAPI app."""
        self.app = FastAPI()
        self.app.include_router(roaming_router)
        self.client = TestClient(self.app)
        
        # Set test admin key
        os.environ["ODIN_ADMIN_KEY"] = "test-admin-key"
        os.environ["ODIN_GATEWAY_BASE_URL"] = "https://test-gw.example.com"
    
    def test_mint_pass_endpoint(self):
        """Test pass minting endpoint."""
        response = self.client.post(
            "/v1/roaming/pass",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "did": "did:odin:agent-123",
                "aud": "https://visited-gw.example.com",
                "realm_dst": "banking",
                "scope": ["mesh:post", "translate:read"],
                "ttl_seconds": 300
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "pass" in data
        assert "exp" in data
        assert "jti" in data
        assert data["scope"] == ["mesh:post", "translate:read"]
        assert data["realm_dst"] == "banking"
        
        # Verify token format
        pass_token = data["pass"]
        assert len(pass_token.split('.')) == 3
    
    def test_mint_pass_unauthorized(self):
        """Test pass minting without admin key."""
        response = self.client.post(
            "/v1/roaming/pass",
            json={
                "did": "did:odin:agent-123",
                "aud": "https://visited-gw.example.com",
                "realm_dst": "banking",
                "scope": ["mesh:post"],
                "ttl_seconds": 300
            }
        )
        
        assert response.status_code == 401
    
    def test_mint_pass_invalid_did(self):
        """Test pass minting with invalid DID."""
        response = self.client.post(
            "/v1/roaming/pass",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "did": "invalid-did-format",
                "aud": "https://visited-gw.example.com",
                "realm_dst": "banking",
                "scope": ["mesh:post"],
                "ttl_seconds": 300
            }
        )
        
        assert response.status_code == 400
        assert "Invalid DID format" in response.json()["detail"]
    
    def test_mint_pass_invalid_scope(self):
        """Test pass minting with invalid scope."""
        response = self.client.post(
            "/v1/roaming/pass",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "did": "did:odin:agent-123",
                "aud": "https://visited-gw.example.com",
                "realm_dst": "banking",
                "scope": ["invalid:scope"],
                "ttl_seconds": 300
            }
        )
        
        assert response.status_code == 400
        assert "Invalid scope" in response.json()["detail"]
    
    def test_get_roaming_config(self):
        """Test getting roaming configuration."""
        response = self.client.get(
            "/v1/roaming/config",
            headers={"X-Admin-Key": "test-admin-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "version" in data
        assert "issuers_count" in data
        assert "issuers" in data


class TestRoamingReceipts:
    """Test roaming receipt generation."""
    
    def test_create_roaming_receipt_block(self):
        """Test roaming receipt block creation."""
        claims = {
            "iss": "https://home-gw.example.com",
            "sub": "did:odin:agent-123",
            "aud": "https://visited-gw.example.com",
            "realm_src": "business",
            "realm_dst": "banking",
            "scope": ["mesh:post", "translate:read"],
            "jti": "01JC4QK5EHQ3TH0N3W2W1H3Z2B",
            "exp": 1755739200,
            "verified": True
        }
        
        receipt_block = create_roaming_receipt_block(claims, True)
        
        assert receipt_block["iss"] == "https://home-gw.example.com"
        assert receipt_block["sub"] == "did:odin:agent-123"
        assert receipt_block["verified"] is True
        assert receipt_block["scope"] == ["mesh:post", "translate:read"]
        assert "exp" in receipt_block  # Should be ISO formatted


class TestHELIntegration:
    """Test HEL policy integration."""
    
    def test_roaming_valid_predicate(self):
        """Test roaming.valid HEL predicate."""
        valid_claims = {"verified": True, "exp": int(time.time()) + 300}
        invalid_claims = {"verified": False}
        
        assert roaming_valid(valid_claims) is True
        assert roaming_valid(invalid_claims) is False
        assert roaming_valid({}) is False
    
    def test_roaming_scope_contains_predicate(self):
        """Test roaming.scope_contains HEL predicate."""
        claims = {"scope": ["mesh:post", "translate:read"]}
        
        assert roaming_scope_contains(claims, "mesh:post") is True
        assert roaming_scope_contains(claims, "translate:read") is True
        assert roaming_scope_contains(claims, "admin:write") is False
        assert roaming_scope_contains({}, "mesh:post") is False


class TestEndToEndRoaming:
    """End-to-end roaming tests."""
    
    def setup_method(self):
        """Set up E2E test environment."""
        self.home_private_key, self.home_public_key = generate_ed25519_keypair()
        self.home_generator = RoamingPassGenerator(
            gateway_base_url="https://home-gw.example.com",
            private_key=self.home_private_key,
            kid="home-key-2025"
        )
        
        # Set up visited gateway verifier
        trust_anchor = TrustAnchor(
            name="trusted-home",
            iss="https://home-gw.example.com",
            discovery="https://home-gw.example.com/.well-known/odin/discovery.json",
            realms_allowed=["business", "banking"],
            audience_allowed=["https://visited-gw.example.com"],
            max_ttl_seconds=600
        )
        
        config = RoamingConfig(version=1, issuers=[trust_anchor])
        self.visited_verifier = RoamingPassVerifier(config, "https://visited-gw.example.com")
    
    def test_happy_path_roaming(self):
        """Test complete happy path roaming flow."""
        # 1. Home Gateway mints pass
        pass_token, metadata = self.home_generator.mint_pass(
            agent_did="did:odin:agent-123",
            audience="https://visited-gw.example.com",
            realm_dst="banking",
            scope=["mesh:post", "translate:read"],
            ttl_seconds=300,
            realm_src="business"
        )
        
        assert pass_token is not None
        assert metadata["realm_dst"] == "banking"
        
        # 2. Visited Gateway verifies pass
        with patch.object(self.visited_verifier, '_get_public_key', return_value=self.home_public_key):
            valid, claims, error = self.visited_verifier.verify_pass(
                roaming_pass=pass_token,
                agent_did="did:odin:agent-123",
                target_realm="banking",
                requested_operation="mesh:post"
            )
        
        assert valid is True
        assert error is None
        assert claims["sub"] == "did:odin:agent-123"
        assert claims["realm_dst"] == "banking"
        
        # 3. Create receipt block
        receipt_block = create_roaming_receipt_block(claims, True)
        
        assert receipt_block["verified"] is True
        assert receipt_block["iss"] == "https://home-gw.example.com"
        assert receipt_block["realm_src"] == "business"
        assert receipt_block["realm_dst"] == "banking"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
