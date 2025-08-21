# ODIN Protocol - Enterprise AI Communication Network

<div align="center">

![ODIN Protocol](https://img.shields.io/badge/ODIN-Protocol-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.0.0-green?style=for-the-badge)
![Beta](https://img.shields.io/badge/0.9.0--beta-features-orange?style=for-the-badge)
![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=for-the-badge)
![Build](https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge)

**🚀 Production-Ready AI Communication Network | Enterprise Security | OpenAI Compatible**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [API Reference](#-api-reference)

</div>

---

## 🎯 What is ODIN?

ODIN (Open Decentralized Intelligence Network) is a **production-grade AI communication network** that enables secure, authenticated interaction between AI agents across organizational boundaries. Every message is cryptographically signed, typed, and auditable with complete proof validation.

### 🏆 Why Choose ODIN?

- ✅ **114 Production Endpoints** - Complete service mesh with enterprise features
- ✅ **OpenAI Compatible** - Drop-in replacement with enhanced security  
- ✅ **Enterprise Security** - HTTP signatures, proof envelopes, policy enforcement
- ✅ **Cloud Native** - Google Cloud ready, Kubernetes & Cloud Run optimized
- ✅ **Strategic Business Features** - RTN transparency, Federation settlement, Payment processing

A production-ready implementation of the ODIN Protocol enabling secure, authenticated communication between AI agents across organizational boundaries with full proof-of-work validation and transform receipt capabilities.

## 🚀 Quick Demo

```bash
# Start ODIN Gateway (114 endpoints)
python -m apps.gateway.api

# Send a message with proof verification
curl -X POST http://localhost:8080/v1/envelope \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello ODIN!"}'

# Bridge to another realm
curl -X POST http://localhost:8080/bridge/partner-realm \
  -H "Content-Type: application/json" \
  -d '{"message": "Cross-realm communication"}'

# Access strategic business features
curl -X GET http://localhost:8080/rtn/receipts     # RTN transparency
curl -X GET http://localhost:8080/federation/status  # Settlement network
curl -X POST http://localhost:8080/payments/bridge  # Payment processing
```

## 🔥 Strategic Business Features

<table>
<tr>
<td width="33%">

### 🧾 **RTN - Receipts Transparency Network**
- **9 API endpoints** for receipt verification
- **Blockchain transparency** for transaction audit
- **Real-time verification** of business receipts  
- **Compliance tracking** for regulatory requirements
- **Multi-format support** (PDF, JSON, XML)

</td>
<td width="33%">

### 🌐 **Federation & Settlement** 
- **11 API endpoints** for cross-network settlement
- **Multi-party reconciliation** across organizations
- **Automated settlement** with proof validation
- **Real-time balance tracking** and reporting
- **Enterprise integration** with existing systems

</td>
<td width="33%">

### 💳 **Payments Bridge Pro**
- **8 API endpoints** for payment processing
- **ISO 20022 compliance** for banking integration
- **ACH NACHA processing** with batch management  
- **SFTP connectivity** for secure file transfer
- **Enterprise payment workflows** with audit trails

</td>
</tr>
</table>

## 📋 Repository Structure

```
ODIN Protocol Implementation
├── 🏗️ Core Services
│   ├── apps/gateway/          # Main FastAPI gateway (114 endpoints)
│   ├── apps/agent_beta/       # OpenAI-compatible proxy
│   └── services/relay/        # Secure HTTP forwarder
├── 📚 Strategic Business Libraries  
│   ├── libs/odin_core/odin/rtn/              # RTN transparency (9 endpoints)
│   ├── libs/odin_core/odin/federation/       # Settlement network (11 endpoints)
│   ├── libs/odin_core/odin/payments_bridge_pro/  # Payment processing (8 endpoints)
│   └── libs/odin_core/        # Protocol implementation (OML-C, OPE, JWKS)
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
- **114 Active Endpoints** for complete enterprise service mesh
- **Strategic Business APIs** - RTN, Federation, Payments integration
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
- **Enhanced HEL Middleware** with 9-layer security

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
- **Carrier-grade security** architecture

</td>
<td>

### 📊 **Enterprise Features**
- **Prometheus Observability** 
- **Structured Logging** with correlation IDs
- **Health Checks** and diagnostics
- **Auto-scaling** Cloud Run deployment
- **Marketplace Integration**
- **Business process automation**

</td>
</tr>
</table>

## 🧪 0.9.0-beta Features

**Verifiable Agent Identity (VAI) System:**
- Agent registration and approval workflow
- X-ODIN-Agent header validation middleware  
- Firestore-backed agent registry with admin APIs
- Route-specific agent enforcement

**Software Bill of Materials (SBOM):**
- X-ODIN-Model, X-ODIN-Tool, X-ODIN-Prompt-CID header processing
- Automatic receipt enhancement with SBOM metadata
- Compliance tracking for AI model usage

**Merkle-Stream Receipts (Optional):**
- `/v1/mesh/stream` endpoint for streaming data
- Merkle root calculation for stream verification
- Real-time receipt generation with cryptographic proofs

> 📖 See [0.9.0-beta Configuration Guide](./docs/0_9_0_BETA_CONFIG.md) for setup instructions

## 🏗️ Complete Implementation

This repository contains a comprehensive ODIN Protocol implementation with:

- **114 Active Gateway Endpoints** - Complete FastAPI service mesh with strategic business features
- **Agent Beta Service** - OpenAI-compatible proxy with HTTP signature enforcement
- **Strategic Business APIs** - RTN transparency (9 endpoints), Federation settlement (11 endpoints), Payment processing (8 endpoints)
- **Bridge Functionality** - Cross-realm mesh communication with hop forwarding
- **Marketplace Integration** - Google Cloud Marketplace ready deployment
- **Production Observability** - Prometheus metrics, structured logging, distributed tracing
- **Enhanced Security** - Carrier-grade security with 9-layer HEL middleware

## 🚀 Core Services

### Gateway Service (`apps/gateway/`)
Complete FastAPI application with 114 endpoints including:

**Strategic Business APIs:**
- **RTN (Receipts Transparency Network)** (`/rtn/*`) - 9 endpoints for receipt verification and blockchain transparency
- **Federation & Settlement** (`/federation/*`) - 11 endpoints for cross-network settlement and reconciliation  
- **Payments Bridge Pro** (`/payments/*`) - 8 endpoints for ISO 20022 and ACH NACHA payment processing

**Core Infrastructure:**
- **Bridge & Mesh** (`/bridge/*`, `/mesh/*`) - Cross-realm communication
- **Service Registry** (`/registry/*`) - Agent capability discovery  
- **Transform Receipts** (`/receipts/*`, `/transform/*`) - Message transformation tracking
- **Proof Management** (`/proof/*`, `/envelope/*`) - OPE validation and storage
- **Admin APIs** (`/admin/*`) - Runtime configuration and health
- **SFT Translation** (`/sft/*`) - Semantic format transformation

### Agent Beta Service (`apps/agent_beta/`)
OpenAI-compatible service with:
- HTTP signature authentication enforcement
- Prometheus metrics integration
- Complete API compatibility layer
- Security middleware stack

### Core Libraries (`libs/odin_core/`)
Production-ready protocol implementation:
- **OML-C**: ODIN Message Layer with Content addressing
- **OPE**: ODIN Proof Envelopes for message integrity
- **JWKS**: JSON Web Key Set management and rotation
- **RTN**: Receipts Transparency Network with blockchain verification
- **Federation**: Cross-network settlement and reconciliation engine
- **Payments Bridge Pro**: ISO 20022 and ACH NACHA payment processing
- **Storage**: Pluggable backends (Local, GCS, Firestore)
- **Transform**: Message transformation and receipt generation
- **Bridge**: Mesh networking and hop forwarding

## 📦 Architecture

```
ODIN Protocol Stack
├── Gateway (114 endpoints)
│   ├── Strategic Business APIs
│   │   ├── RTN - Receipts Transparency (9 endpoints)
│   │   ├── Federation - Settlement Network (11 endpoints)
│   │   └── Payments Bridge Pro (8 endpoints)
│   ├── Core Infrastructure
│   │   ├── Bridge & Mesh Communication
│   │   ├── Service Registry & Discovery  
│   │   ├── Transform Receipt Management
│   │   ├── Proof Envelope Validation
│   │   └── Admin & Monitoring APIs
├── Agent Beta (OpenAI Proxy)
│   ├── HTTP Signature Enforcement
│   ├── Enhanced HEL Middleware (9 layers)
│   ├── Metrics & Observability
│   └── Security Middleware
├── Core Libraries
│   ├── OML-C Message Layer
│   ├── OPE Proof System
│   ├── JWKS Key Management
│   ├── Strategic Business Services
│   ├── Storage Abstraction
│   └── Transform Engine
└── Infrastructure
    ├── Cloud Run Deployment
    ├── Helm Charts
    ├── Prometheus Monitoring
    └── Marketplace Packaging
```

## 🔧 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+ (for JS SDK)
- Docker (for containerized deployment)

### Local Development
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run gateway service
python -m apps.gateway.api

# Run agent beta service  
python -m apps.agent_beta

# Run tests
python -m pytest
npm -C packages/sdk test
```

### Production Deployment
```bash
# Deploy to Cloud Run
./scripts/deploy-cloudrun.ps1

# Deploy with Helm
helm install odin-gateway helm/odin-gateway-relay/
```

## 🔐 Security Features

- **HTTP Signature Authentication** - RFC 9421 compliant request signing
- **Proof Envelope Validation** - Cryptographic message integrity
- **Policy Enforcement** - Runtime policy evaluation and enforcement  
- **Response Signing** - Gateway response authentication
- **Tenant Isolation** - Multi-tenant quota and access control

## 🌐 Middleware Stack

- **Proof Enforcement** - Validates ODIN Proof Envelopes
- **HTTP Signature Enforcement** - Authenticates requests via signatures
- **Response Signing** - Signs gateway responses for verification
- **Tenant Management** - Multi-tenant isolation and quota
- **Metrics Collection** - Prometheus observability

## 📊 Observability

- **Prometheus Metrics** - Request/response metrics, proof validation stats
- **Structured Logging** - JSON formatted logs with correlation IDs
- **Health Checks** - Comprehensive health and readiness endpoints
- **Admin APIs** - Runtime configuration and diagnostic endpoints

## 🔄 Bridge & Mesh

- **Cross-Realm Communication** - Route messages between different ODIN realms
- **Hop Forwarding** - Multi-hop message routing with proof chains
- **Mesh Discovery** - Automatic peer discovery and route optimization
- **Transform Receipts** - Track message transformations across hops

## 📋 API Reference

### Gateway Endpoints (114 total)
```
/health                    - Service health check
/bridge/{target}          - Bridge message to target realm
/mesh/forward             - Mesh network forwarding

Strategic Business APIs:
/rtn/receipts             - RTN receipt verification (9 endpoints)
/federation/settlement    - Cross-network settlement (11 endpoints)  
/payments/bridge          - Payment processing APIs (8 endpoints)

Core Infrastructure:
/registry/agents          - Agent capability registry
/receipts/transform       - Transform receipt management
/proof/verify             - Proof envelope validation
/admin/reload             - Runtime configuration reload
/sft/translate           - Semantic format transformation
... and 86 more endpoints
```

### Agent Beta Endpoints
```
/v1/chat/completions     - OpenAI-compatible chat API
/v1/models               - Available model listing
/health                  - Service health check
/metrics                 - Prometheus metrics
```

## 🧪 Testing

Comprehensive test suite with 100+ test cases:

```bash
# Python tests (gateway, core, agent beta)
python -m pytest

# JavaScript SDK tests  
npm -C packages/sdk test

# E2E integration tests
python -m pytest tests/e2e/

# Run specific test suites
python -m pytest apps/gateway/tests/
python -m pytest apps/agent_beta/tests/
python -m pytest libs/odin_core/tests/
```

## 📦 Packages & SDKs

### JavaScript SDK (`packages/sdk/`)
- Complete TypeScript implementation
- ODIN Proof Envelope validation
- Discovery client for service registry
- Browser and Node.js compatible

### Langchain Tools (`packages/langchain-odin-tools/`)
- Pre-built Langchain tool integrations
- Echo and translate tools
- TypeScript type definitions

### Python SDK (`sdks/python/`)
- Native Python ODIN client
- CID content addressing
- Proof verification utilities

## 🏢 Marketplace Integration

Google Cloud Marketplace ready with:

- **Cloud Run Deployment** - Production containerized deployment
- **Helm Charts** - Kubernetes orchestration
- **IAM Integration** - Google Cloud identity integration  
- **Monitoring Setup** - Cloud Operations integration
- **Security Policies** - Cloud Armor protection

## 🔧 Configuration

### Environment Variables
```bash
# Storage Backend
ODIN_STORAGE_BACKEND=firestore  # local, gcs, firestore

# Security
ODIN_JWKS_URL=https://keys.example.com/.well-known/jwks.json
ODIN_ENFORCE_SIGNATURES=true

# Observability  
ODIN_METRICS_ENABLED=true
ODIN_LOG_LEVEL=INFO

# Bridge Configuration
ODIN_BRIDGE_TARGET_OVERRIDE=https://partner.odin.network
ODIN_HOP_HEADERS=x-odin-hop-count,x-odin-route-id
```

### Realm Packs (`packs/realms/`)
- **Banking Realm** - Financial service integration with PCI compliance
- **Business Realm** - General business process automation
- Template system for custom realm development

## 🚀 Production Features

- **High Availability** - Load balanced gateway deployment
- **Auto Scaling** - Cloud Run automatic scaling  
- **Monitoring** - Comprehensive Prometheus metrics
- **Security** - HTTP signature enforcement and policy validation
- **Multi-tenant** - Tenant isolation and quota management
- **Compliance** - Audit logging and proof archival

## 📈 Performance

- **Gateway Throughput** - 1000+ requests/second per instance across 114 endpoints
- **Strategic Business Processing** - Sub-second RTN verification, real-time settlement, instant payment validation
- **Proof Validation** - Sub-millisecond verification
- **Storage Backends** - Optimized for GCS and Firestore
- **Caching** - Intelligent caching for discovery and proofs
- **Enterprise Scale** - Multi-tenant architecture with carrier-grade performance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`python -m pytest && npm -C packages/sdk test`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](./LICENSE) file for details.

## 🔗 Related Projects

- [ODIN Protocol Specification](https://odin-protocol.org)
- [ODIN JavaScript SDK](./packages/sdk/)
- [ODIN Langchain Tools](./packages/langchain-odin-tools/)

---

**Production Ready** ✅ | **Enterprise Grade** ✅ | **Strategic Business Features** ✅
