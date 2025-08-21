# 🚀 ODIN Protocol - Enterprise AI Infrastructure Platform

<div align="center">

[![CI/CD Pipeline](https://github.com/Maverick0351a/ODINAIMESH/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Maverick0351a/ODINAIMESH/actions/workflows/ci-cd.yml)
[![Deploy to Cloud Run](https://github.com/Maverick0351a/ODINAIMESH/actions/workflows/deploy.yml/badge.svg)](https://github.com/Maverick0351a/ODINAIMESH/actions/workflows/deploy.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/typescript-5.0%2B-blue.svg)](https://typescriptlang.org)

**Production-ready enterprise AI infrastructure providing secure, verifiable, and compliant AI-to-AI communication at scale.**

[🏗️ Architecture](#️-architecture) • [🚀 Quick Start](#-quick-start) • [💰 Revenue Models](#-revenue-models) • [📚 Documentation](#-documentation)

</div>

---

## 🎯 Overview

ODIN Protocol is a comprehensive enterprise AI platform that enables organizations to deploy AI systems with cryptographic proof of execution, full audit trails, and zero-trust security. Built for financial institutions, payment processors, and enterprise customers requiring regulatory compliance.

### 🏆 Key Features

- **🔒 Zero-Trust Security**: Cryptographic proof chains, HTTP signatures, JWKS rotation
- **🏢 Strategic Business APIs**: 28 endpoints for enterprise automation (RTN, Federation, Payments)
- **💰 Revenue-Ready**: Bridge Pro ($2k-10k/mo), Research Engine subscriptions
- **📈 Production Scale**: 1000+ req/sec, auto-scaling, comprehensive monitoring
- **🌐 Multi-Cloud**: Google Cloud Platform with AWS/Azure support planned

### 🌍 Live Production Services

| Service | URL | Status |
|---------|-----|--------|
| **Gateway** | https://odin-gateway-125773133762.us-central1.run.app | ✅ Live |
| **Agent Beta** | https://odin-agent-beta-125773133762.us-central1.run.app | ✅ Live |
| **Documentation** | https://odin-site-125773133762.us-central1.run.app | ✅ Live |

## 🚀 Quick Start

### Try the Live Production API
```bash
# Test health endpoint
curl https://odin-gateway-125773133762.us-central1.run.app/health

# Send a message with proof verification
curl -X POST https://odin-gateway-125773133762.us-central1.run.app/v1/envelope \
  -H "Content-Type: application/json" \
  -d '{"intent": "echo", "payload": {"message": "Hello ODIN!"}}'

# Access strategic business features
curl https://odin-gateway-125773133762.us-central1.run.app/rtn/health
curl https://odin-gateway-125773133762.us-central1.run.app/federation/health  
curl https://odin-gateway-125773133762.us-central1.run.app/payments/health

# OpenAI-compatible endpoint
curl -X POST https://odin-agent-beta-125773133762.us-central1.run.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Local Development
```bash
# Clone repository
git clone https://github.com/Maverick0351a/ODINAIMESH.git
cd ODINAIMESH

# Install dependencies
pip install -r requirements.txt
cd packages/sdk && npm install && cd ../..

# Start development server
python -m uvicorn apps.gateway.api:app --reload --port 8000
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

```

## 💰 Revenue Models

### 🏦 Bridge Pro - Enterprise Payment Processing
- **Target Market**: Financial institutions, payment processors  
- **Pricing**: $2,000 - $10,000/month
- **Features**: ISO 20022, approval workflows, compliance reporting
- **Scalability**: Per-transaction pricing for high volume

### 🧪 Research Engine - Multi-tenant AI Platform  
- **Free Tier**: 1 project, 1,000 requests/month
- **Pro Tier**: $29/month - 10 projects, 50,000 requests
- **Enterprise Tier**: $299/month - Unlimited projects, dedicated support
- **Add-ons**: Additional compute, storage, priority support

### 🎮 BYOM Playground - Lead Generation
- **Strategy**: Free secure model testing → Research Engine conversion
- **Features**: 15-minute tokens, real-time testing, embedded CTAs
- **Metrics**: Lead capture, conversion tracking, usage analytics

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

## � Documentation

### 🌍 Live Documentation
- **[Production Site](https://odin-site-125773133762.us-central1.run.app)** - Interactive guides and examples
- **[API Explorer](https://odin-gateway-125773133762.us-central1.run.app/docs)** - Swagger UI for all 114 endpoints
- **[Strategic Business APIs](https://odin-gateway-125773133762.us-central1.run.app/redoc)** - RTN, Federation, Payments documentation

### 📖 Comprehensive Guides
- **[Complete Feature Overview](COMPREHENSIVE_README.md)** - Detailed technical documentation (718 lines)
- **[Getting Started Guide](docs/getting-started.md)** - Quick start tutorial
- **[Security Implementation](docs/security.md)** - Zero-trust security details
- **[Deployment Guide](marketplace/CLOUDRUN.md)** - Production deployment instructions
- **[Repository Inventory](docs/REPO_INVENTORY.md)** - Complete codebase overview

### 🛠️ Developer Resources
- **[TypeScript SDK](packages/sdk/)** - `@odin-protocol/sdk` NPM package
- **[LangChain Tools](packages/langchain-odin-tools/)** - `@odin-protocol/langchain-tools`
- **[Python Examples](sdks/python/)** - Python integration examples
- **[CI/CD Pipeline](.github/workflows/)** - GitHub Actions deployment

## �📋 API Reference

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
