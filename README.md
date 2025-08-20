# ODIN Protocol

An "AI intranet" for governed, auditable AI-to-AI messaging. ODIN is a network fabric where every message is typed, signed, translated, and traceable end-to-end. It ships two core services:

- Gateway: a policy-guarded router/transformer with discovery, verification, translation, response signing, receipts, and metrics.
- Relay: a hardened HTTP byte-forwarder with OPE proof verification, SSRF controls, retries, and optional Google ID token injection.

---

## Overview

ODIN Protocol enables secure, compliant interoperability between AI systems. Each request/response is:
- Typed (OML schemas),
- Signed (Ed25519 OPE proofs),
- Translated (SFT maps/registry), and
- Audited (persisted receipts and hop chains).

The Gateway exposes governance-aware endpoints for discovery, verification, translation, and mesh forwarding. The Relay provides a minimal, policy-safe egress path with verification, rate limiting, and SSRF defense.

---

## Key Features

### Gateway
- Discovery: `/.well-known/odin/discovery.json` — advertises capabilities, public keys, and policy flags.
- JWKS: `/.well-known/jwks.json` — Ed25519 public keys for verification.
- Dynamic reload — HEL policy and SFT maps/registry can be reloaded without restarting.
- Translate — schema translation with provable transform receipts.
- Verify — CID/signature verification endpoint.
- Hop receipts + chain retrieval:
  - `GET /v1/receipts/hops` — list hop receipts.
  - `GET /v1/receipts/hops/chain/{trace_id}` — reconstruct multi-hop chains.
- Mesh forward: `POST /v1/mesh/forward` — SSRF guard, multi-hop receipts, and forwarding across the mesh.
- Optional envelope echo: `POST /v1/envelope` — cross-router testing utility.
- Response signing — ODIN response-signing headers for downstream verification.
- Prometheus metrics at `/metrics` — standardized `odin_http_*`, `odin_hops_total`, and failure/ops counters.

### Relay
- Single endpoint: `POST /relay` with:
  - Token-bucket rate limiting.
  - SSRF guard (deny-link-local/metadata/private IPs; test overrides available).
  - Allowed header forwarding (e.g., `x-odin-oml-cid`, `x-odin-ope`, and related ODIN headers).
  - OPE proof verification.
  - Optional Google ID token injection (for calling secured upstreams).
  - Retries with backoff and per-request timeouts.
- Optional Prometheus metrics at `/metrics` (relay-specific families).

---

## Architecture
- Receipts persistence: pluggable storage. Defaults to in-memory; adapters available/ready for Firestore and GCS. TTL metadata supported.
- Multi-hop audit trails: transform receipts + hop index enable end-to-end trace chains across multiple services/hops.
- Dynamic config reload: HEL policy and SFT assets can be reloaded on demand for rapid governance updates without rolling restarts.
- JWKS cache & rotation: verifier caches JWKS with TTL and supports rotation grace using previous snapshots.
- Defense-in-depth: SSRF guard, rate limiting, response signing, and strict header allow-lists.

---

## Why It Matters
- Interoperability: Translate between OML schemas to connect heterogeneous AI agents and services.
- Trust & compliance: Cryptographic receipts and verifiable signatures provide auditability and non-repudiation.
- Governance: Enforce HEL policy at the perimeter and adapt quickly via dynamic reload.
- Observability: Rich Prometheus metrics, receipts, and hop chains offer production-grade visibility.

---

## How to Run

### Quick start (local)
```powershell
# Generic example
uvicorn main:app --reload --port 8080
```

### Services (recommended during development)
- Gateway (FastAPI app):
```powershell
# From repo root
uvicorn apps.gateway.api:app --reload --port 8080
```

- Relay (FastAPI app):
```powershell
# From repo root
uvicorn services.relay.api:app --reload --port 8081
```

If needed, install dependencies first:
```powershell
pip install -r requirements.txt
```

### Environment variables
Common runtime knobs (non-exhaustive):
- `ODIN_STORAGE` — storage backend selector (in-memory, gcs, firestore, etc.).
- `ODIN_POLICY_URI` — HEL policy location.
- `ODIN_SFT_REGISTRY_URI` — SFT registry location.
- `ODIN_SFT_MAP_DIR` — directory of SFT maps.
- `ODIN_ADMIN_KEY` — admin auth key for reload endpoints.
- `ODIN_ALLOW_TEST_HOSTS` — allow test hosts/bypass SSRF blocks in test mode (true/1 for CI/dev).
- `ODIN_GATEWAY_RATE_LIMIT_QPS` — per-IP rate limit for the Gateway.
- `ODIN_RELAY_RATE_LIMIT_QPS` — per-IP rate limit for the Relay.
- Tenant guardrails (Gateway):
  - `ODIN_TENANT_HEADER` — header name to read tenant id (default `X-ODIN-Tenant`).
  - `ODIN_TENANT_REQUIRED=1` — require tenant header on most routes (health/metrics/docs exempt).
  - `ODIN_TENANT_ALLOWED=tenantA,tenantB` — allow-list of tenant ids (optional).
  - `ODIN_TENANT_RATE_LIMIT_QPS=5` — per-tenant QPS token bucket (0 disables; <0 blocks all).
  - `ODIN_TENANT_QUOTA_MONTHLY_REQUESTS=10000` — per-tenant monthly quota (requests). Set to 0 or unset to disable.
  - `ODIN_TENANT_QUOTA_OVERRIDES="acme=5000,globex=20000"` — per-tenant monthly quota overrides.
- Admin SSO/IAP (Gateway, optional):
  - `ODIN_REQUIRE_IAP=1` — enforce Cloud IAP/SSO identity for admin routes.
  - `ODIN_ADMIN_ALLOWED_EMAILS=a@x.com,b@y.org` — exact email allow-list.
  - `ODIN_ADMIN_ALLOWED_DOMAINS=example.com,acme.org` — domain allow-list.
- `JWKS_CACHE_TTL` — JWKS cache TTL (seconds).
- `ROTATION_GRACE_SEC` — JWKS rotation grace window (seconds).
- `ODIN_OTEL` — enable OpenTelemetry tracing when not "0" (default off).
- `ODIN_OTEL_EXPORTER` — "gcp" to use Cloud Trace exporter when GOOGLE_CLOUD_PROJECT is set; otherwise OTLP HTTP exporter is used by default (honors standard OTLP envs).

Additional Google Cloud integration variables may be required when enabling ID token injection or Cloud Run (e.g., credentials and target audience), depending on your environment.

### Metrics
- Gateway metrics at `/metrics`: standardized HTTP metrics plus:
  - `odin_hops_total` — hop receipts emitted.
  - `odin_receipt_write_failures_total{kind}` — receipt persistence failures.
  - `odin_dynamic_reload_total{target}` — dynamic reload invocations.
  - `odin_tenant_http_requests_total{tenant,path,method}` and `odin_tenant_http_request_seconds{tenant,...}` — per-tenant HTTP metrics.
  - `odin_tenant_quota_consumed_total{tenant}` and `odin_tenant_quota_blocked_total{tenant}` — quota consumption and blocks.
- Relay metrics at `/metrics` (optional): relay HTTP metrics, SSRF/rate-limit counters, and retry/timeout observations.

### Headers and receipts
- Response hop headers: `X-ODIN-Trace-Id`, `X-ODIN-Hop-Id`, `X-ODIN-Forwarded-By` for 200 responses where applicable.
- Receipts endpoints: `GET /v1/receipts/hops`, `GET /v1/receipts/hops/chain/{trace_id}`.
  - Filter hops/chain by tenant (optional): `?tenant=acme` when listing with `expand=true` or fetching a chain.
  - Hop receipts include `tenant` field when present; storage metadata includes `odin_tenant`.

### Cloud Run (optional)
- Deploy Gateway and Relay as separate services.
- Recommended: configure min instances for cold-start mitigation, set request/CPU limits, and enable Cloud Armor/WAF in front.
- Export `/metrics` to your observability stack; consider managed Prometheus.
- To enable tracing on Cloud Run, set `ODIN_OTEL=1` and either `ODIN_OTEL_EXPORTER=gcp` (Cloud Trace) or configure OTLP endpoint via standard `OTEL_EXPORTER_OTLP_ENDPOINT` env.

---

## Getting Started with SDKs (Python & Node.js)

Note: These SDKs are published as preview builds. APIs may change before 1.0.

### Python

Install (core primitives + HTTP client):
```powershell
pip install odin-protocol-sdk
```

Quick start (discovery-aware client):
```python
from odin_protocol_sdk.client import OdinHttpClient  # provided by the SDK package

client = OdinHttpClient.from_discovery("http://127.0.0.1:8080", require_proof=True)

# Echo envelope (useful for cross-router tests)
payload = {"text": "hello"}
data, verification = client.post_envelope("/v1/envelope", payload)
print("ok:", verification.ok, "cid:", verification.oml_cid)

# Translate with transform receipts
req = {
    "payload": {"intent": "alpha@v1.hello", "args": {"text": "hi"}},
    "from_sft": "alpha@v1",
    "to_sft": "beta@v1"
}
resp = client.post_json("/v1/translate", req)
print("translated:", resp["payload"])  # SDK typically verifies response headers/signature
```

Verify offline using core primitives:
```python
from odin_protocol_sdk.verify import verify

envelope = {"ope": "...b64...", "oml_c_b64": "..."}
r = verify(envelope=envelope, jwks="http://127.0.0.1:8080/.well-known/jwks.json")
print(r.ok, r.reason)
```

### Node.js / TypeScript

Install:
```bash
npm install odin-protocol-sdk
# or: yarn add odin-protocol-sdk
```

Quick start:
```ts
import { OdinClient } from "odin-protocol-sdk";

const client = await OdinClient.fromDiscovery("http://127.0.0.1:8080", { requireProof: true });

const payload = { text: "hello" };
const { data, verification } = await client.postEnvelope("/v1/envelope", payload);
console.log(verification.ok, verification.omlCid);

const translateReq = {
  payload: { intent: "alpha@v1.hello", args: { text: "hi" } },
  from_sft: "alpha@v1",
  to_sft: "beta@v1",
};
const translated = await client.postJson("/v1/translate", translateReq);
console.log(translated.payload);
```

Tips:
- Prefer discovery: `/.well-known/odin/discovery.json` provides JWKS URL, capabilities, and policy flags so the SDK can auto-configure proof expectations.
- Handle 429 (rate limit) and 400/502 (relay/gateway errors) with simple retries and backoff.
- When calling secured upstreams via the gateway/relay, set an audience if you enable ID token injection.

Troubleshooting:
- `missing_oml_c` or `content_hash_mismatch`: ensure the payload you verify matches the exact bytes that were signed; prefer using the SDK’s built-in verification of responses.
- `target not allowed`: SSRF guard blocked your URL; set `ODIN_ALLOW_TEST_HOSTS=1` in dev/CI or use public hosts.
- `rate_limited`: lower QPS or increase `ODIN_GATEWAY_RATE_LIMIT_QPS`/`ODIN_RELAY_RATE_LIMIT_QPS` in non-production environments.
  - On Windows VS Code task runner, prefer cross-shell or PowerShell-friendly commands:
    - SDK tests task: `npm -C packages/sdk test --silent`

---

## Operations: usage snapshot

- Endpoint: `GET /billing/usage`
  - Returns current-month per-tenant request usage from the in-process quota middleware (if enabled). Example:
    `{ "month": "2025-08", "tenants": { "acme": 123, "globex": 42 } }`
  - Intended for ops visibility; not a billing-source-of-truth.

---

## Status
- Tests: unit/integration tests passing.
- Deployments: Gateway and Relay confirmed on Cloud Run.
- Enterprise-readiness (in progress):
  - Observability dashboards and runbooks.
  - Perimeter security hardening (Cloud Armor/WAF).
  - Marketplace/enterprise packaging.

---

## License
TBD. Contact the maintainers for licensing details.
