"""
Simple roaming system validation test
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'libs', 'odin_core'))

def test_roaming_pass_generation():
    """Test basic pass generation."""
    from odin.roaming import generate_ed25519_keypair, RoamingPassGenerator
    
    # Generate keypair
    private_key, public_key = generate_ed25519_keypair()
    
    # Create generator
    generator = RoamingPassGenerator(
        gateway_base_url="https://home-gw.example.com",
        private_key=private_key,
        kid="test-key-2025"
    )
    
    # Generate pass
    pass_token, metadata = generator.mint_pass(
        agent_did="did:odin:agent-123",
        audience="https://visited-gw.example.com",
        realm_dst="banking",
        scope=["mesh:post", "translate:read"],
        ttl_seconds=300
    )
    
    # Validate format
    assert isinstance(pass_token, str)
    assert len(pass_token.split('.')) == 3  # header.payload.signature
    
    # Validate metadata
    assert "exp" in metadata
    assert "jti" in metadata
    assert metadata["scope"] == ["mesh:post", "translate:read"]
    assert metadata["realm_dst"] == "banking"
    
    print("✅ Pass generation test passed")
    return True

def test_roaming_config_loading():
    """Test configuration loading."""
    from odin.roaming import TrustAnchor, RoamingConfig
    
    # Create trust anchor
    trust_anchor = TrustAnchor(
        name="test-issuer",
        iss="https://test.example.com",
        discovery="https://test.example.com/.well-known/odin/discovery.json",
        realms_allowed=["test"],
        audience_allowed=["https://visited.example.com"],
        max_ttl_seconds=300
    )
    
    # Create config
    config = RoamingConfig(version=1, issuers=[trust_anchor])
    
    assert config.version == 1
    assert len(config.issuers) == 1
    assert config.issuers[0].name == "test-issuer"
    
    print("✅ Configuration loading test passed")
    return True

def test_hel_integration():
    """Test HEL predicate functions."""
    from odin.roaming import roaming_valid, roaming_scope_contains
    import time
    
    # Test valid roaming claims
    valid_claims = {"verified": True, "exp": int(time.time()) + 300}
    invalid_claims = {"verified": False}
    
    assert roaming_valid(valid_claims) is True
    assert roaming_valid(invalid_claims) is False
    assert roaming_valid({}) is False
    
    # Test scope checking
    claims_with_scope = {"scope": ["mesh:post", "translate:read"]}
    
    assert roaming_scope_contains(claims_with_scope, "mesh:post") is True
    assert roaming_scope_contains(claims_with_scope, "translate:read") is True
    assert roaming_scope_contains(claims_with_scope, "admin:write") is False
    assert roaming_scope_contains({}, "mesh:post") is False
    
    print("✅ HEL integration test passed")
    return True

def test_receipt_generation():
    """Test receipt block generation."""
    from odin.roaming import create_roaming_receipt_block
    import time
    
    claims = {
        "iss": "https://home-gw.example.com",
        "sub": "did:odin:agent-123",
        "aud": "https://visited-gw.example.com",
        "realm_src": "business",
        "realm_dst": "banking",
        "scope": ["mesh:post", "translate:read"],
        "jti": "01JC4QK5EHQ3TH0N3W2W1H3Z2B",
        "exp": int(time.time()) + 300,
        "verified": True
    }
    
    receipt_block = create_roaming_receipt_block(claims, True)
    
    assert receipt_block["iss"] == "https://home-gw.example.com"
    assert receipt_block["sub"] == "did:odin:agent-123"
    assert receipt_block["verified"] is True
    assert receipt_block["scope"] == ["mesh:post", "translate:read"]
    assert "exp" in receipt_block  # Should be ISO formatted
    
    print("✅ Receipt generation test passed")
    return True

if __name__ == "__main__":
    print("🚀 Running ODIN Roaming System Validation Tests")
    print("=" * 50)
    
    try:
        test_roaming_pass_generation()
        test_roaming_config_loading()
        test_hel_integration()
        test_receipt_generation()
        
        print("=" * 50)
        print("✅ All tests passed! Roaming system is functional.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
