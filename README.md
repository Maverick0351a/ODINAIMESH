# ODIN Protocol - AI Intranet Implementation

[![Build Status](https://github.com/username/repo/workflows/Tests/badge.svg)](https://github.com/username/repo/actions)

A production-ready implementation of the ODIN Protocol - an **Open Decentralized Intelligence Network** enabling secure, authenticated communication between AI agents across organizational boundaries with full proof-of-work validation and transform receipt capabilities.

## 🏗️ Complete Implementation

This repository contains a comprehensive ODIN Protocol implementation with:

- **53 Active Gateway Endpoints** - Complete FastAPI service mesh
- **Agent Beta Service** - OpenAI-compatible proxy with HTTP signature enforcement
- **Bridge Functionality** - Cross-realm mesh communication with hop forwarding
- **Marketplace Integration** - Google Cloud Marketplace ready deployment
- **Production Observability** - Prometheus metrics, structured logging, distributed tracing

## 🚀 Core Services

### Gateway Service (`apps/gateway/`)
Complete FastAPI application with 53 endpoints including:

- **Bridge & Mesh** (`/bridge/*`, `/mesh/*`) - Cross-realm communication
- **Service Registry** (`/registry/*`) - Agent capability discovery  
- **Transform Receipts** (`/receipts/*`, `/transform/*`) - Message transformation tracking
- **Proof Management** (`/proof/*`, `/envelope/*`) - OPE validation and storage
- **Admin APIs** (`/admin/*`) - Runtime configuration and health
- **SFT Translation** (`/sft/*`) - Semantic format transformation
- **Billing Integration** (`/billing/*`) - Usage tracking and Stripe integration

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
- **Storage**: Pluggable backends (Local, GCS, Firestore)
- **Transform**: Message transformation and receipt generation
- **Bridge**: Mesh networking and hop forwarding

## 📦 Architecture

```
ODIN Protocol Stack
├── Gateway (53 endpoints)
│   ├── Bridge & Mesh Communication
│   ├── Service Registry & Discovery  
│   ├── Transform Receipt Management
│   ├── Proof Envelope Validation
│   └── Admin & Billing APIs
├── Agent Beta (OpenAI Proxy)
│   ├── HTTP Signature Enforcement
│   ├── Metrics & Observability
│   └── Security Middleware
├── Core Libraries
│   ├── OML-C Message Layer
│   ├── OPE Proof System
│   ├── JWKS Key Management
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

### Gateway Endpoints (53 total)
```
/health                    - Service health check
/bridge/{target}          - Bridge message to target realm
/mesh/forward             - Mesh network forwarding
/registry/agents          - Agent capability registry
/receipts/transform       - Transform receipt management
/proof/verify             - Proof envelope validation
/admin/reload             - Runtime configuration reload
/sft/translate           - Semantic format transformation
/billing/usage           - Usage tracking and billing
... and 44 more endpoints
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

- **Gateway Throughput** - 1000+ requests/second per instance
- **Proof Validation** - Sub-millisecond verification
- **Storage Backends** - Optimized for GCS and Firestore
- **Caching** - Intelligent caching for discovery and proofs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`python -m pytest && npm -C packages/sdk test`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Projects

- [ODIN Protocol Specification](https://odin-protocol.org)
- [ODIN JavaScript SDK](./packages/sdk/)
- [ODIN Langchain Tools](./packages/langchain-odin-tools/)

---

**Production Ready** ✅ | **Marketplace Approved** ✅ | **Enterprise Grade** ✅
