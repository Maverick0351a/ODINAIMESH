# ODIN Protocol - Enterprise AI Intranet

<div align="center">

![ODIN Protocol](https://img.shields.io/badge/ODIN-Protocol-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.0.0-green?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)
![Build](https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge)

**🚀 Production-Ready AI Intranet with 53+ Endpoints | Bridge Networking | OpenAI Compatible**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [API Reference](#-api-reference)

</div>

---

## 🎯 What is ODIN?

ODIN (Open Decentralized Intelligence Network) is a **production-grade AI intranet** that enables secure, authenticated communication between AI agents across organizational boundaries. Every message is cryptographically signed, typed, and auditable.

### 🏆 Why Choose ODIN?

- ✅ **53 Production Endpoints** - Complete service mesh with bridge networking
- ✅ **OpenAI Compatible** - Drop-in replacement with enhanced security  
- ✅ **Enterprise Security** - HTTP signatures, proof envelopes, policy enforcement
- ✅ **Cloud Native** - Google Cloud Marketplace ready, Kubernetes & Cloud Run
- ✅ **Multi-Tenant** - Built-in tenant isolation and quota management

## 🚀 Quick Demo

```bash
# Start ODIN Gateway
python -m apps.gateway.api

# Send a message with proof verification
curl -X POST http://localhost:8080/v1/envelope \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello ODIN!"}'

# Bridge to another realm
curl -X POST http://localhost:8080/bridge/partner-realm \
  -H "Content-Type: application/json" \
  -d '{"message": "Cross-realm communication"}'
```

## 📋 Repository Structure

```
ODIN Protocol Implementation
├── 🏗️ Core Services
│   ├── apps/gateway/          # Main FastAPI gateway (53 endpoints)
│   ├── apps/agent_beta/       # OpenAI-compatible proxy
│   └── services/relay/        # Secure HTTP forwarder
├── 📚 Libraries  
│   ├── libs/odin_core/        # Protocol implementation (OML-C, OPE, JWKS)
│   └── gateway/               # Gateway utilities and constants
├── 🔧 SDKs & Tools
│   ├── packages/sdk/          # TypeScript/JavaScript SDK
│   ├── packages/langchain-odin-tools/  # LangChain integrations
│   └── sdks/python/           # Python SDK
├── ☁️ Infrastructure
│   ├── helm/                  # Kubernetes deployment charts
│   ├── marketplace/           # Google Cloud Marketplace configs
│   └── scripts/               # Deployment and utility scripts
├── 🧪 Testing
│   ├── tests/                 # Integration and E2E tests
│   └── apps/*/tests/          # Service-specific test suites
└── 📦 Configuration
    ├── config/                # Runtime configurations
    └── packs/realms/          # Business domain packages
```

## 🔥 Key Features

<table>
<tr>
<td width="50%">

### 🌐 **Gateway Service**
- **53 Active Endpoints** for complete service mesh
- **Bridge & Mesh Networking** for cross-realm communication  
- **Service Registry** for AI agent discovery
- **Transform Receipts** for message audit trails
- **Admin APIs** for runtime configuration

</td>
<td width="50%">

### 🤖 **Agent Beta Service**  
- **OpenAI API Compatible** - drop-in replacement
- **HTTP Signature Enforcement** for authentication
- **Prometheus Metrics** for observability
- **Security Middleware** stack

</td>
</tr>
<tr>
<td>

### 🔐 **Security Features**
- **Cryptographic Proof Envelopes** (OPE)
- **HTTP Signature Authentication** (RFC 9421)
- **Policy Enforcement Engine** 
- **Response Signing** for verification
- **Multi-tenant Isolation**

</td>
<td>

### 📊 **Enterprise Features**
- **Prometheus Observability** 
- **Structured Logging** with correlation IDs
- **Health Checks** and diagnostics
- **Auto-scaling** Cloud Run deployment
- **Marketplace Integration**

</td>
</tr>
</table>

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+ (for SDK)
- Docker (optional)

### 1️⃣ Installation
```bash
git clone https://github.com/Maverick0351a/ODINAIMESH.git
cd ODINAIMESH
pip install -r requirements.txt
```

### 2️⃣ Run Gateway
```bash
python -m apps.gateway.api
# Gateway running at http://localhost:8080
```

### 3️⃣ Run Agent Beta (OpenAI Compatible)
```bash
python -m apps.agent_beta  
# Agent Beta at http://localhost:8081
```

### 4️⃣ Test the API
```python
from odin_protocol_sdk.client import OdinHttpClient

client = OdinHttpClient.from_discovery("http://localhost:8080")
response = client.post_envelope("/v1/envelope", {"text": "Hello ODIN!"})
print(f"Verified: {response.verification.ok}")
```

## 📚 Documentation

- 📖 [**Complete API Reference**](./docs/) - All 53 endpoints documented
- 🏗️ [**Architecture Guide**](./docs/ARCHITECTURE.md) - System design and components  
- 🔐 [**Security Model**](./docs/SECURITY.md) - Cryptographic foundations
- ☁️ [**Deployment Guide**](./marketplace/) - Cloud Run and Kubernetes
- 🧪 [**Testing Guide**](./docs/TESTING.md) - Running the test suite

## 🌟 Star History

If you find ODIN useful, please ⭐ star this repository!

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](./CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`python -m pytest && npm -C packages/sdk test`)
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## 🔗 Links

- 🌐 [ODIN Protocol Website](https://odin-protocol.org)
- 📚 [Documentation](./docs/)
- 🎯 [Roadmap](./ROADMAP.md)
- 💬 [Discord Community](https://discord.gg/odin-protocol)

---

<div align="center">

**Built with ❤️ for the AI Agent Ecosystem**

[⭐ Star us on GitHub](https://github.com/Maverick0351a/ODINAIMESH) • [🐛 Report Bug](https://github.com/Maverick0351a/ODINAIMESH/issues) • [💡 Request Feature](https://github.com/Maverick0351a/ODINAIMESH/issues)

</div>
