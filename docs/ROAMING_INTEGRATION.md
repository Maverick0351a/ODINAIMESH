# ODIN Roaming Pass Integration Guide

## Overview

The ODIN Roaming Pass system enables secure AI-to-AI communication across different realms and gateways using cryptographically verifiable short-lived tokens. This system implements a telecom-style roaming mechanism where AI agents can obtain "roaming passes" from their home gateway to access resources in visited gateways.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ AI Agent    │────▶│ Home Gateway │────▶│ Roaming     │
│ (Roamer)    │     │              │     │ Pass        │
└─────────────┘     └──────────────┘     └─────────────┘
                            │                     │
                            ▼                     ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Target      │◀────│ Visited      │◀────│ Request     │
│ Resource    │     │ Gateway      │     │ w/ Pass     │
└─────────────┘     └──────────────┘     └─────────────┘
```

## Core Components

### 1. Trust Anchors Configuration

Configure trusted roaming issuers in `configs/roaming/trust_anchors.yaml`:

```yaml
version: 1
issuers:
  - name: "business-realm"
    iss: "https://business-gw.example.com"
    discovery: "https://business-gw.example.com/.well-known/odin/discovery.json"
    realms_allowed: ["business", "enterprise"]
    audience_allowed: ["https://visited-gw.example.com"]
    max_ttl_seconds: 600
    
  - name: "fintech-realm"
    iss: "https://fintech-gw.example.com"
    discovery: "https://fintech-gw.example.com/.well-known/odin/discovery.json"
    realms_allowed: ["banking", "payments"]
    audience_allowed: ["https://visited-gw.example.com"]
    max_ttl_seconds: 300
```

### 2. Roaming Pass Format

Roaming passes use a JWT-like format with three base64url-encoded parts:

```
HEADER.PAYLOAD.SIGNATURE
```

**Header:**
```json
{
  "alg": "EdDSA",
  "typ": "ODIN-Pass",
  "kid": "gateway-key-2025"
}
```

**Payload:**
```json
{
  "iss": "https://home-gw.example.com",
  "sub": "did:odin:agent-123",
  "aud": "https://visited-gw.example.com",
  "realm_src": "business",
  "realm_dst": "banking",
  "scope": ["mesh:post", "translate:read"],
  "jti": "01JC4QK5EHQ3TH0N3W2W1H3Z2B",
  "nbf": 1755738900,
  "exp": 1755739200,
  "bind": {
    "method": "OPE",
    "hash_alg": "sha256"
  }
}
```

## API Integration

### Home Gateway: Minting Passes

**Endpoint:** `POST /v1/roaming/pass`

**Headers:**
```
X-Admin-Key: <admin-key>
Content-Type: application/json
```

**Request:**
```json
{
  "did": "did:odin:agent-123",
  "aud": "https://visited-gw.example.com",
  "realm_dst": "banking",
  "scope": ["mesh:post", "translate:read"],
  "ttl_seconds": 300,
  "realm_src": "business",
  "bind": {
    "method": "OPE",
    "hash_alg": "sha256"
  }
}
```

**Response:**
```json
{
  "pass": "eyJhbGciOiJFZERTQSIsInR5cCI6Ik9ESU4tUGFzcyIsImtpZCI6ImdhdGV3YXkta2V5LTIwMjUifQ.eyJpc3MiOiJodHRwczovL2hvbWUtZ3cuZXhhbXBsZS5jb20iLCJzdWIiOiJkaWQ6b2RpbjphZ2VudC0xMjMiLCJhdWQiOiJodHRwczovL3Zpc2l0ZWQtZ3cuZXhhbXBsZS5jb20iLCJyZWFsbV9zcmMiOiJidXNpbmVzcyIsInJlYWxtX2RzdCI6ImJhbmtpbmciLCJzY29wZSI6WyJtZXNoOnBvc3QiLCJ0cmFuc2xhdGU6cmVhZCJdLCJqdGkiOiIwMUpDNFFLNUVIUTNUSDBOM1cyVzFIM1oyQiIsIm5iZiI6MTc1NTczODkwMCwiZXhwIjoxNzU1NzM5MjAwLCJiaW5kIjp7Im1ldGhvZCI6Ik9QRSIsImhhc2hfYWxnIjoic2hhMjU2In19.signature",
  "exp": 1755739200,
  "jti": "01JC4QK5EHQ3TH0N3W2W1H3Z2B",
  "scope": ["mesh:post", "translate:read"],
  "realm_dst": "banking",
  "metadata": {
    "issued_at": "2025-01-21T10:15:00Z",
    "expires_at": "2025-01-21T10:20:00Z",
    "ttl_seconds": 300
  }
}
```

### Visited Gateway: Using Passes

**Request Header:**
```
X-ODIN-Roaming-Pass: <roaming-pass-token>
```

The visited gateway middleware automatically:
1. Validates the roaming pass signature
2. Checks expiration and timing
3. Verifies agent DID matches
4. Validates realm and scope permissions
5. Sets roaming claims in request context

## HEL Policy Integration

### Available HEL Predicates

#### `roaming.valid(roaming_claims)`
Checks if roaming claims are present and verified:
```javascript
roaming.valid(roaming_claims) && request.realm == "banking"
```

#### `roaming.scope_contains(roaming_claims, scope)`
Checks if roaming scope contains specific permission:
```javascript
roaming.scope_contains(roaming_claims, "mesh:post") || admin.level >= 5
```

#### `roaming.realm_dst(roaming_claims, realm)`
Checks if roaming destination realm matches:
```javascript
roaming.realm_dst(roaming_claims, "banking") && user.verified
```

### Example HEL Policies

**Allow roaming agents to post messages:**
```json
{
  "name": "roaming_mesh_post",
  "condition": "roaming.valid(roaming_claims) && roaming.scope_contains(roaming_claims, 'mesh:post')",
  "effect": "ALLOW",
  "resources": ["mesh/messages"]
}
```

**Restrict translation access to verified roaming:**
```json
{
  "name": "roaming_translate_access",
  "condition": "roaming.valid(roaming_claims) && roaming.scope_contains(roaming_claims, 'translate:read') && roaming.realm_dst(roaming_claims, request.realm)",
  "effect": "ALLOW",
  "resources": ["translate/*"]
}
```

## Security Considerations

### Cryptographic Security
- **Ed25519 Signatures:** All passes are signed with Ed25519 for strong cryptographic security
- **JWKS Discovery:** Public keys are fetched via secure JWKS endpoints
- **Short TTL:** Maximum 600 seconds prevents replay attacks
- **Audience Validation:** Passes are bound to specific gateway audiences

### Trust Management
- **Trust Anchors:** Explicitly configured trusted issuers only
- **Realm Restrictions:** Issuers limited to specific source/destination realms
- **Scope Validation:** Fine-grained permission checking
- **Admin Authentication:** Pass minting requires admin-level access

### Timing Security
- **Not Before (nbf):** Prevents premature use
- **Expiration (exp):** Automatic expiration enforcement  
- **JWT ID (jti):** Unique identifier for tracking/auditing
- **Clock Skew:** 30-second tolerance for time differences

## Error Handling

### Verification Errors

| Error | Description | HTTP Status | Action |
|-------|-------------|-------------|---------|
| `expired` | Pass has expired | 401 | Request new pass |
| `not_yet_valid` | Pass not yet valid (nbf) | 401 | Wait or check clocks |
| `agent_mismatch` | Agent DID doesn't match | 403 | Check DID format |
| `realm_mismatch` | Target realm not allowed | 403 | Request correct realm |
| `scope_mismatch` | Insufficient permissions | 403 | Request broader scope |
| `issuer_not_trusted` | Issuer not in trust anchors | 403 | Configure trust |
| `signature_invalid` | Cryptographic verification failed | 401 | Check key rotation |

### Example Error Response
```json
{
  "error": "roaming_verification_failed",
  "details": {
    "reason": "scope_mismatch",
    "required": "translate:write",
    "available": ["mesh:post", "translate:read"]
  },
  "timestamp": "2025-01-21T10:15:30Z"
}
```

## Implementation Examples

### Python Client (Home Gateway)

```python
from odin.roaming import RoamingPassGenerator

# Initialize generator
generator = RoamingPassGenerator(
    gateway_base_url="https://home-gw.example.com",
    private_key=private_key,
    kid="gateway-key-2025"
)

# Mint roaming pass
pass_token, metadata = generator.mint_pass(
    agent_did="did:odin:agent-123",
    audience="https://visited-gw.example.com",
    realm_dst="banking", 
    scope=["mesh:post", "translate:read"],
    ttl_seconds=300
)

print(f"Roaming pass: {pass_token}")
print(f"Expires at: {metadata['exp']}")
```

### FastAPI Middleware (Visited Gateway)

```python
from gateway.middleware.roaming import RoamingMiddleware
from odin.roaming import load_roaming_config

# Load trust configuration
config = load_roaming_config("configs/roaming/trust_anchors.yaml")

# Initialize middleware
roaming_middleware = RoamingMiddleware(
    config=config,
    gateway_base_url="https://visited-gw.example.com"
)

# Add to FastAPI app
app.add_middleware(RoamingMiddleware, config=config, gateway_base_url="https://visited-gw.example.com")
```

### JavaScript/Node.js Client

```javascript
// Making authenticated request with roaming pass
const response = await fetch('https://visited-gw.example.com/v1/mesh/messages', {
  method: 'POST',
  headers: {
    'X-ODIN-Roaming-Pass': roamingPassToken,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    content: "Hello from roaming agent!",
    realm: "banking"
  })
});

if (response.status === 401) {
  console.log('Roaming pass expired, requesting new one...');
  // Request new pass from home gateway
}
```

## Metrics and Monitoring

### Key Metrics

- **Pass Mint Rate:** Number of passes minted per minute
- **Verification Success Rate:** Percentage of successful verifications
- **Rejection Reasons:** Breakdown of verification failures
- **TTL Distribution:** Average and percentile TTL usage
- **Cross-Realm Traffic:** Volume by realm pair

### Log Formats

**Pass Minting:**
```json
{
  "event": "roaming_pass_minted",
  "timestamp": "2025-01-21T10:15:00Z",
  "agent_did": "did:odin:agent-123",
  "audience": "https://visited-gw.example.com",
  "realm_dst": "banking",
  "scope": ["mesh:post", "translate:read"],
  "ttl_seconds": 300,
  "jti": "01JC4QK5EHQ3TH0N3W2W1H3Z2B"
}
```

**Pass Verification:**
```json
{
  "event": "roaming_pass_verified",
  "timestamp": "2025-01-21T10:16:00Z",
  "result": "success",
  "agent_did": "did:odin:agent-123", 
  "issuer": "https://home-gw.example.com",
  "realm_dst": "banking",
  "operation": "mesh:post",
  "jti": "01JC4QK5EHQ3TH0N3W2W1H3Z2B"
}
```

## Testing

### Unit Tests
```bash
# Run roaming-specific tests
python -m pytest tests/test_roaming.py -v

# Run with coverage
python -m pytest tests/test_roaming.py --cov=odin.roaming --cov-report=html
```

### Integration Tests
```bash
# Test end-to-end roaming flow
python -m pytest tests/test_roaming.py::TestEndToEndRoaming -v

# Test HEL integration
python -m pytest tests/test_roaming.py::TestHELIntegration -v
```

### Load Testing
```bash
# Test pass minting performance
python scripts/load_test_roaming.py --passes-per-second 100 --duration 60

# Test verification performance  
python scripts/load_test_roaming.py --verify-only --rate 500 --duration 30
```

## Troubleshooting

### Common Issues

**Clock Skew Problems:**
- Ensure NTP synchronization across gateways
- Check for timezone mismatches
- Adjust `nbf` tolerance if needed

**JWKS Discovery Failures:**
- Verify discovery endpoint accessibility
- Check SSL certificate validity
- Ensure CORS configuration if cross-origin

**Scope Permission Errors:**
- Review scope naming conventions
- Check realm-to-scope mappings
- Validate HEL policy configurations

**High Latency:**
- Enable JWKS caching
- Consider pass pre-minting for known agents
- Optimize trust anchor configuration

## Future Extensions

### Planned Features
- **Pass Renewal:** Automatic renewal before expiration
- **Batch Minting:** Multiple passes in single request
- **Conditional Binding:** Dynamic proof-of-possession
- **Audit Trails:** Complete roaming transaction logs
- **Federation:** Multi-hop roaming across gateway chains

### Integration Roadmap
- **OAuth2 Integration:** Standard OAuth2 flow compatibility
- **SAML Federation:** Enterprise SSO integration
- **Blockchain Anchoring:** Immutable roaming audit trails
- **Zero-Knowledge Proofs:** Privacy-preserving agent verification

## References

- [ODIN Gateway Architecture](./BRIDGES.md)
- [HEL Policy Engine](./docs/HEL_POLICY.md)
- [Agent DID Specification](./docs/AGENT_DIDS.md)
- [Ed25519 Cryptography](https://tools.ietf.org/html/rfc8032)
- [JWT Specification](https://tools.ietf.org/html/rfc7519)
