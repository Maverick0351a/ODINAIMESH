# 0.9.0-beta Configuration Guide

This document describes the configuration options for the new 0.9.0-beta features: VAI (Verifiable Agent Identity), SBOM capture, and Merkle-Stream receipts.

## 🎯 VAI (Verifiable Agent Identity)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAI_BACKEND` | `firestore` | Backend for agent registry (`firestore` or `memory`) |
| `VAI_HEADER_NAME` | `X-ODIN-Agent` | Header name for agent identification |
| `VAI_REQUIRE` | `0` | Require VAI for all requests (`1` to enable) |
| `VAI_ENFORCE_ROUTES` | `""` | Comma-separated routes that require VAI |
| `GOOGLE_CLOUD_PROJECT` | - | GCP project for Firestore backend |

### Usage Examples

```bash
# Enable VAI for specific routes
export VAI_ENFORCE_ROUTES="/v1/envelope,/v1/translate"

# Require VAI for all requests
export VAI_REQUIRE=1

# Use memory backend for development
export VAI_BACKEND=memory
```

### Agent Management Workflow

1. **Register Agent** (admin required):
   ```bash
   curl -X POST http://localhost:8080/v1/admin/agents \
     -H "X-ODIN-Admin-Key: ${ODIN_ADMIN_KEY}" \
     -H "Content-Type: application/json" \
     -d '{
       "agent_id": "my-ai-agent",
       "public_key": "dGVzdC1wdWJsaWMta2V5",
       "metadata": {
         "name": "My AI Agent",
         "version": "1.0.0",
         "description": "Production AI agent"
       }
     }'
   ```

2. **Approve Agent** (admin required):
   ```bash
   curl -X PUT http://localhost:8080/v1/admin/agents/my-ai-agent/status \
     -H "X-ODIN-Admin-Key: ${ODIN_ADMIN_KEY}" \
     -H "Content-Type: application/json" \
     -d '{
       "status": "approved",
       "approved_by": "admin@company.com"
     }'
   ```

3. **Use Agent** (include in requests):
   ```bash
   curl -X POST http://localhost:8080/v1/envelope \
     -H "X-ODIN-Agent: my-ai-agent" \
     -H "Content-Type: application/json" \
     -d '{"intent": "echo", "message": "hello"}'
   ```

### Admin Endpoints

- `POST /v1/admin/agents` - Register new agent
- `GET /v1/admin/agents` - List agents (supports `?status=pending`)
- `GET /v1/admin/agents/{agent_id}` - Get specific agent
- `PUT /v1/admin/agents/{agent_id}/status` - Update agent status
- `DELETE /v1/admin/agents/{agent_id}` - Delete agent
- `GET /v1/admin/agents/health` - VAI system health check

## 📋 SBOM (Software Bill of Materials)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ODIN_SBOM_ENABLED` | `1` | Enable SBOM processing (`0` to disable) |
| `ODIN_SBOM_MODEL_HEADER` | `X-ODIN-Model` | Header for AI model identifiers |
| `ODIN_SBOM_TOOL_HEADER` | `X-ODIN-Tool` | Header for tool/function identifiers |
| `ODIN_SBOM_PROMPT_HEADER` | `X-ODIN-Prompt-CID` | Header for prompt content IDs |

### Usage Examples

```bash
# Include SBOM headers in requests
curl -X POST http://localhost:8080/v1/envelope \
  -H "X-ODIN-Model: gpt-4,claude-3" \
  -H "X-ODIN-Tool: search,calculator,weather" \
  -H "X-ODIN-Prompt-CID: bafybeiabc123def456" \
  -H "Content-Type: application/json" \
  -d '{"intent": "analyze", "data": "sample"}'
```

### Receipt Enhancement

When SBOM headers are present, receipts will include an `sbom` field:

```json
{
  "payload": {"intent": "analyze", "data": "sample"},
  "proof": {"oml_cid": "...", "kid": "...", "ope": "..."},
  "sbom": {
    "models": ["gpt-4", "claude-3"],
    "tools": ["search", "calculator", "weather"],
    "prompt_cids": ["bafybeiabc123def456"]
  }
}
```

### Metrics

SBOM processing generates metrics for observability:

- `odin_sbom_headers_total{type="model"}` - Count of model headers processed
- `odin_sbom_headers_total{type="tool"}` - Count of tool headers processed  
- `odin_sbom_headers_total{type="prompt_cid"}` - Count of prompt CID headers processed

## 🌊 Merkle-Stream Receipts

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ODIN_STREAMING_ENABLED` | `0` | Enable streaming endpoints (`1` to enable) |
| `ODIN_STREAM_CHUNK_SIZE` | `1024` | Default chunk size for streaming |
| `ODIN_STREAM_MAX_CHUNK_SIZE` | `10000` | Maximum allowed chunk size |
| `ODIN_STREAM_DELAY_MS` | `0` | Artificial delay between chunks (testing) |

### Usage Examples

```bash
# Enable streaming
export ODIN_STREAMING_ENABLED=1

# Start a stream
curl -X POST http://localhost:8080/v1/mesh/stream \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"items": [1,2,3,4,5,6,7,8,9,10]},
    "chunk_size": 3,
    "include_merkle": true
  }'
```

### Stream Response

Streaming responses include:

- `X-ODIN-Stream-Id` - Unique stream identifier
- `X-ODIN-Trace-Id` - Trace ID for correlation
- `X-ODIN-Stream-Root` - Merkle root hash (if enabled)

Response body contains JSON chunks:

```
data: {"sequence": 0, "data": {"items": [1,2,3]}, "timestamp": 1234567890, "hash": "abc123..."}

data: {"sequence": 1, "data": {"items": [4,5,6]}, "timestamp": 1234567891, "hash": "def456..."}

data: {"type": "odin.stream.receipt", "stream_id": "stream-123", "merkle_root": "789abc..."}
```

### Stream Receipts

Final stream receipts include complete metadata:

```json
{
  "type": "odin.stream.receipt",
  "stream_id": "stream-1640995200-abc123",
  "trace_id": "trace-456def",
  "merkle_root": "a1b2c3d4e5f6...",
  "chunk_count": 4,
  "start_ts": 1640995200000,
  "end_ts": 1640995205000,
  "duration_ms": 5000,
  "chunks": [
    {"sequence": 0, "hash": "chunk0hash...", "timestamp": 1640995201000},
    {"sequence": 1, "hash": "chunk1hash...", "timestamp": 1640995202000}
  ]
}
```

## 🔄 Integration with Existing Features

### Middleware Order

The 0.9.0-beta features integrate into the existing middleware stack:

1. `TenantMiddleware` - Multi-tenant isolation
2. `TenantQuotaMiddleware` - Quota enforcement  
3. **`VAIMiddleware`** - Agent identity validation (NEW)
4. `ProofEnforcementMiddleware` - ODIN proof validation
5. `HttpSignEnforcementMiddleware` - HTTP signature validation
6. `ResponseSigningMiddleware` - Response signing
7. `ProofDiscoveryMiddleware` - Header augmentation

### Discovery Integration

The `/.well-known/odin/discovery.json` endpoint includes 0.9.0-beta capabilities:

```json
{
  "version": "0.9.0-beta",
  "features": {
    "vai": {"enabled": true, "enforce_routes": ["/v1/envelope"]},
    "sbom": {"enabled": true, "headers": ["X-ODIN-Model", "X-ODIN-Tool", "X-ODIN-Prompt-CID"]},
    "streaming": {"enabled": false}
  }
}
```

### Metrics Integration

All 0.9.0-beta features integrate with the existing Prometheus metrics:

- `odin_vai_requests_total{agent_id, status, path}` - VAI validation results
- `odin_sbom_headers_total{type}` - SBOM header processing
- `odin_hops_total{route="mesh.stream"}` - Streaming requests

## 🚀 Production Deployment

### Firestore Setup (VAI)

```bash
# Enable Firestore API
gcloud services enable firestore.googleapis.com

# Create database (if not exists)
gcloud firestore databases create --region=us-central

# Set up IAM for Cloud Run
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

### Environment Template

```bash
# Core ODIN settings
export ODIN_ADMIN_KEY="secure-admin-key-here"
export GOOGLE_CLOUD_PROJECT="your-project-id"

# 0.9.0-beta: VAI settings
export VAI_BACKEND="firestore"
export VAI_ENFORCE_ROUTES="/v1/envelope,/v1/translate"

# 0.9.0-beta: SBOM settings  
export ODIN_SBOM_ENABLED="1"

# 0.9.0-beta: Streaming (optional)
export ODIN_STREAMING_ENABLED="0"  # Enable only if needed

# Existing ODIN settings
export ODIN_ENFORCE_ROUTES="/v1/envelope"
export ODIN_HTTP_SIGN_ENFORCE_ROUTES="/v1/admin"
```

### Health Checks

Monitor 0.9.0-beta features via health endpoints:

```bash
# Overall gateway health
curl http://localhost:8080/health

# VAI system health (admin required)
curl -H "X-ODIN-Admin-Key: $ODIN_ADMIN_KEY" \
  http://localhost:8080/v1/admin/agents/health
```

## 🔧 Troubleshooting

### Common Issues

1. **VAI agent not found**: Ensure agent is registered and approved
2. **Firestore permission denied**: Check service account IAM roles
3. **SBOM headers not processed**: Verify `ODIN_SBOM_ENABLED=1`
4. **Streaming endpoint 501**: Enable with `ODIN_STREAMING_ENABLED=1`

### Debug Commands

```bash
# Check agent status
curl -H "X-ODIN-Admin-Key: $ODIN_ADMIN_KEY" \
  http://localhost:8080/v1/admin/agents/my-agent

# Test SBOM processing
curl -X POST http://localhost:8080/v1/envelope \
  -H "X-ODIN-Model: debug-model" \
  -d '{"intent": "test"}'

# Verify metrics
curl http://localhost:8080/metrics | grep -E "(vai|sbom)"
```

## 📚 Additional Resources

- [ODIN Protocol Specification](../README.md)
- [Agent Registry API Reference](../docs/vai-api.md)
- [SBOM Header Standards](../docs/sbom-spec.md)
- [Streaming Protocol](../docs/streaming-spec.md)
