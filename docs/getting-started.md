# Getting Started

Welcome to ODIN Protocol! This guide will have you running secure AI-to-AI communication in under 5 minutes.

## Quick Deploy

### Option 1: Google Cloud Run (Recommended)

Deploy directly to Google Cloud with our one-click button:

<div class="deploy-section">
  <a href="https://deploy.cloud.run/?git_repo=https://github.com/ODIN-PROTOCOL/odin-protocol" class="deploy-button">
    <img src="https://deploy.cloud.run/button.svg" alt="Run on Google Cloud" />
  </a>
</div>

This will:
- ✅ Deploy ODIN Gateway & Relay to Cloud Run
- ✅ Set up SSL/TLS termination
- ✅ Configure environment variables
- ✅ Enable health checks and monitoring

### Option 2: Docker

For local development or custom deployments:

```bash
# Clone the repository
git clone https://github.com/ODIN-PROTOCOL/odin-protocol.git
cd odin-protocol

# Start with Docker Compose
docker-compose up -d

# Verify deployment
curl http://localhost:8080/health
```

### Option 3: Python Package

Install ODIN as a Python package:

```bash
pip install odin-protocol

# Start the gateway
odin-gateway --port 8080

# Start the relay (separate terminal)
odin-relay --port 8081
```

## First Steps

### 1. Verify Your Deployment

Check that your ODIN gateway is running:

```bash
curl https://your-gateway-url/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.9.0",
  "components": {
    "gateway": "active",
    "relay": "active",
    "metrics": "enabled"
  }
}
```

### 2. Install SDK

Choose your preferred language:

<div class="sdk-tabs">
  <div class="sdk-tab">
    <h4>JavaScript/TypeScript</h4>
    
```bash
npm install @odin-protocol/sdk
```

```typescript
import { OdinClient } from '@odin-protocol/sdk';

const client = new OdinClient({
  gateway: 'https://your-gateway-url',
  apiKey: 'your-api-key'
});

// Send a message
const response = await client.send({
  to: 'ai-agent-123',
  type: 'task.request',
  payload: { action: 'analyze', data: 'sample' }
});
```
  </div>
  
  <div class="sdk-tab">
    <h4>Python</h4>
    
```bash
pip install odin-protocol-sdk
```

```python
from odin_sdk import OdinClient

client = OdinClient(
    gateway='https://your-gateway-url',
    api_key='your-api-key'
)

# Send a message
response = client.send(
    to='ai-agent-123',
    type='task.request',
    payload={'action': 'analyze', 'data': 'sample'}
)
```
  </div>
  
  <div class="sdk-tab">
    <h4>REST API</h4>
    
```bash
curl -X POST https://your-gateway-url/v1/messages \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "ai-agent-123",
    "type": "task.request",
    "payload": {
      "action": "analyze",
      "data": "sample"
    }
  }'
```
  </div>
</div>

### 3. Create Your First Realm Pack

Realm Packs define how messages are routed and processed. Create a simple pack:

```bash
# Generate a starter pack
odin pack init my-first-pack

# Edit the configuration
cat > configs/realms/my-first-pack.json << EOF
{
  "name": "my-first-pack",
  "version": "1.0.0",
  "routes": [
    {
      "match": { "type": "task.*" },
      "target": "local.processor",
      "transforms": ["log", "validate"]
    }
  ],
  "transforms": {
    "log": {
      "type": "log",
      "level": "info"
    },
    "validate": {
      "type": "schema",
      "schema": {
        "type": "object",
        "required": ["action"]
      }
    }
  }
}
EOF

# Deploy the pack
odin pack deploy my-first-pack
```

### 4. Send Your First Message

Test your configuration:

```bash
# Using the CLI
odin send \
  --to "local.processor" \
  --type "task.test" \
  --payload '{"action": "hello", "message": "world"}'

# Expected output:
# ✅ Message sent successfully
# 📨 ID: msg_abc123def456
# 🔗 Receipt: https://your-gateway/receipts/msg_abc123def456
```

## Next Steps

### Explore Features

<div class="feature-grid">
  <div class="feature-card">
    <h4>🔐 Security & Compliance</h4>
    <p>Learn about JWKS rotation, SSRF protection, and audit trails.</p>
    <a href="/docs/security">Security Guide →</a>
  </div>
  
  <div class="feature-card">
    <h4>📊 Monitoring & Metrics</h4>
    <p>Set up Prometheus metrics and health monitoring.</p>
    <a href="/docs/monitoring">Monitoring Guide →</a>
  </div>
  
  <div class="feature-card">
    <h4>🌐 Roaming Federation</h4>
    <p>Enable cross-tenant AI-to-AI communication.</p>
    <a href="/docs/roaming">Roaming Guide →</a>
  </div>
  
  <div class="feature-card">
    <h4>🏦 Bridge Pro (Enterprise)</h4>
    <p>ISO 20022 payment processing for enterprise finance.</p>
    <a href="/docs/bridges#payments-bridge-pro">Bridge Pro →</a>
  </div>
</div>

### Sample Applications

<div class="sample-apps">
  <div class="sample-app">
    <h4>💬 Multi-Agent Chat</h4>
    <p>Coordinate multiple AI agents in real-time conversations.</p>
    <a href="https://github.com/ODIN-PROTOCOL/examples/tree/main/multi-agent-chat">View Example →</a>
  </div>
  
  <div class="sample-app">
    <h4>🤖 Task Orchestration</h4>
    <p>Build complex workflows with multiple AI processing steps.</p>
    <a href="https://github.com/ODIN-PROTOCOL/examples/tree/main/task-orchestration">View Example →</a>
  </div>
  
  <div class="sample-app">
    <h4>📈 Analytics Pipeline</h4>
    <p>Stream data through AI agents for real-time analysis.</p>
    <a href="https://github.com/ODIN-PROTOCOL/examples/tree/main/analytics-pipeline">View Example →</a>
  </div>
</div>

## Configuration Reference

### Environment Variables

Core configuration options:

```bash
# Gateway Configuration
ODIN_GATEWAY_PORT=8080
ODIN_GATEWAY_HOST=0.0.0.0
ODIN_API_KEY=your-secure-api-key

# Relay Configuration  
ODIN_RELAY_PORT=8081
ODIN_RELAY_UPSTREAM=https://your-gateway-url

# Security
ODIN_JWKS_URL=https://your-auth-provider/.well-known/jwks.json
ODIN_ADMIN_KEY=your-admin-key

# Monitoring
ODIN_METRICS_ENABLED=true
ODIN_HEALTH_CHECK_INTERVAL=30s

# Optional: Cloud-specific
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Realm Pack Structure

```json
{
  "name": "pack-name",
  "version": "1.0.0",
  "description": "Pack description",
  "routes": [
    {
      "match": { "type": "message.type.*" },
      "target": "destination.agent",
      "transforms": ["transform1", "transform2"],
      "policy": {
        "rateLimit": "100/hour",
        "auth": "required"
      }
    }
  ],
  "transforms": {
    "transform1": {
      "type": "schema",
      "schema": { "type": "object" }
    }
  },
  "agents": {
    "destination.agent": {
      "endpoint": "https://agent-url",
      "auth": { "type": "bearer", "token": "${AGENT_TOKEN}" }
    }
  }
}
```

## Troubleshooting

### Common Issues

<div class="troubleshooting">
  <div class="issue">
    <h4>❌ Connection Refused</h4>
    <p><strong>Problem:</strong> Can't connect to gateway</p>
    <p><strong>Solution:</strong> Check that the gateway is running and accessible on the correct port</p>
    
```bash
# Check if service is running
curl http://localhost:8080/health

# Check Docker containers
docker ps | grep odin

# Check logs
docker logs odin-gateway
```
  </div>
  
  <div class="issue">
    <h4>❌ Authentication Failed</h4>
    <p><strong>Problem:</strong> API key not accepted</p>
    <p><strong>Solution:</strong> Verify your API key is correct and has proper permissions</p>
    
```bash
# Test authentication
curl -H "Authorization: Bearer your-api-key" \
  https://your-gateway/v1/auth/verify

# Check admin key if needed
curl -H "X-Admin-Key: your-admin-key" \
  https://your-gateway/admin/status
```
  </div>
  
  <div class="issue">
    <h4>❌ Message Routing Failed</h4>
    <p><strong>Problem:</strong> Messages not reaching destination</p>
    <p><strong>Solution:</strong> Check realm pack configuration and target agent availability</p>
    
```bash
# List active realm packs
odin pack list

# Validate pack configuration
odin pack validate my-pack

# Check routing table
curl https://your-gateway/admin/routes
```
  </div>
</div>

### Getting Help

<div class="help-section">
  <div class="help-option">
    <h4>📚 Documentation</h4>
    <p>Comprehensive guides and API reference</p>
    <a href="/docs">Browse Docs →</a>
  </div>
  
  <div class="help-option">
    <h4>💬 Community</h4>
    <p>Join our Discord for real-time support</p>
    <a href="https://discord.gg/odin-protocol">Join Discord →</a>
  </div>
  
  <div class="help-option">
    <h4>🐛 Bug Reports</h4>
    <p>Report issues on GitHub</p>
    <a href="https://github.com/ODIN-PROTOCOL/odin-protocol/issues">Create Issue →</a>
  </div>
  
  <div class="help-option">
    <h4>💼 Enterprise Support</h4>
    <p>Premium support for Pro and Enterprise customers</p>
    <a href="mailto:support@odin-protocol.dev">Contact Support →</a>
  </div>
</div>

---

<div class="next-steps-cta">
  <h2>Ready to build something amazing?</h2>
  <p>You now have everything you need to start building secure AI-to-AI communication with ODIN Protocol.</p>
  <div class="next-steps-buttons">
    <a href="/docs/api" class="cta-button">Explore API Reference</a>
    <a href="https://github.com/ODIN-PROTOCOL/examples" class="cta-button-secondary">View Examples</a>
  </div>
</div>

<style>
.deploy-section {
  text-align: center;
  margin: 2rem 0;
  padding: 2rem;
  background: var(--vp-c-bg-soft);
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
}

.deploy-button img {
  height: 40px;
  transition: transform 0.2s ease;
}

.deploy-button:hover img {
  transform: scale(1.05);
}

.sdk-tabs {
  margin: 2rem 0;
}

.sdk-tab {
  margin: 1.5rem 0;
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.sdk-tab h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.feature-card {
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.feature-card h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.feature-card p {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-2);
}

.feature-card a {
  color: var(--vp-c-brand);
  text-decoration: none;
  font-weight: 600;
}

.feature-card a:hover {
  text-decoration: underline;
}

.sample-apps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.sample-app {
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.sample-app h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.sample-app p {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-2);
}

.sample-app a {
  color: var(--vp-c-brand);
  text-decoration: none;
  font-weight: 600;
}

.troubleshooting {
  margin: 2rem 0;
}

.issue {
  margin: 2rem 0;
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border-left: 4px solid var(--vp-c-brand);
}

.issue h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-1);
}

.issue p {
  margin: 0.5rem 0;
}

.issue strong {
  color: var(--vp-c-brand);
}

.help-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.help-option {
  padding: 1.5rem;
  background: var(--vp-c-bg-soft);
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
  text-align: center;
}

.help-option h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.help-option p {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-2);
}

.help-option a {
  color: var(--vp-c-brand);
  text-decoration: none;
  font-weight: 600;
}

.next-steps-cta {
  text-align: center;
  padding: 3rem 2rem;
  background: var(--vp-c-brand-soft);
  border-radius: 12px;
  margin: 3rem 0;
}

.next-steps-cta h2 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-brand);
}

.next-steps-cta p {
  margin: 0 0 2rem 0;
  color: var(--vp-c-text-2);
  font-size: 1.1rem;
}

.next-steps-buttons {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.cta-button {
  background: var(--vp-c-brand);
  color: white !important;
  padding: 1rem 2rem;
  border-radius: 8px;
  text-decoration: none !important;
  font-weight: 600;
  transition: background 0.2s ease;
  display: inline-block;
}

.cta-button:hover {
  background: var(--vp-c-brand-dark);
}

.cta-button-secondary {
  background: transparent;
  color: var(--vp-c-brand) !important;
  padding: 1rem 2rem;
  border: 2px solid var(--vp-c-brand);
  border-radius: 8px;
  text-decoration: none !important;
  font-weight: 600;
  transition: all 0.2s ease;
  display: inline-block;
}

.cta-button-secondary:hover {
  background: var(--vp-c-brand);
  color: white !important;
}
</style>
