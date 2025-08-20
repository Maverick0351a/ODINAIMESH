# AI Intranet Readiness Checklist

This repo provides a strong core for an internal “AI intranet”: Gateway (governance/translation/receipts) + Relay (hardened egress) with receipts, policy toggles, and metrics. Use this checklist to harden for an enterprise pilot or production.

## Identity and Access
- Inbound auth (Cloud Run):
  - Enforce authenticated invokers on both services; avoid unauthenticated URLs.
  - Optionally front with Cloud IAP or an internal proxy for SSO (OIDC/SAML).
- Service-to-service auth:
  - Keep ODIN_RELAY_ID_TOKEN!=0 and use ODIN_ID_TOKEN_AUDIENCE for upstreams.
  - For Gateway bridge/mesh, set ODIN_BRIDGE_ID_TOKEN/ODIN_MESH_ID_TOKEN as needed.
- Admin endpoints:
  - Require ODIN_ENABLE_ADMIN=1 only when needed; set ODIN_ADMIN_TOKEN via Secret Manager and rotate.

## Policy and Governance
- Proof and signature gates:
  - Enable proof enforcement for sensitive routes: ODIN_ENFORCE_ROUTES, ODIN_ENFORCE_REQUIRE.
  - Enable response signing on write endpoints: ODIN_SIGN_ROUTES, ODIN_SIGN_EMBED.
  - Optional HTTP-sign enforcement: ODIN_HTTP_SIGN_ENFORCE_ROUTES.
- HEL policy:
  - Provide config/hel_policy.json (or URI) and use dynamic reload endpoints for updates.
- Tenancy:
  - Adopt a tenant-id in requests/receipts; partition storage namespaces per tenant.

## Network and Egress
- SSRF guard: already enabled in Relay; keep ODIN_ALLOW_TEST_HOSTS=0 in prod.
- Rate limiting:
  - Set ODIN_GATEWAY_RATE_LIMIT_QPS and ODIN_RELAY_RATE_LIMIT_QPS per environment.
- Perimeter:
  - Add Cloud Armor/WAF before the Gateway; restrict by CIDR, methods, and path allow-list.
  - Prefer Private Service Connect or VPC-only access for internal services.

## Data and Keys
- Receipts and ledger storage:
  - Configure Firestore/GCS backends (see README and marketplace docs). Set TTLs/collections.
- Keys/JWKS:
  - Use a keystore via Secret Manager (ODIN_KEYSTORE_JSON) or mount a keystore file (ODIN_KEYSTORE_PATH).
  - Set JWKS cache knobs: JWKS_CACHE_TTL, ROTATION_GRACE_SEC; plan key rotation.
- Secrets:
  - Store all tokens/keys in Secret Manager; inject as env secrets in Cloud Run.

## Observability and Ops
- Metrics:
  - Scrape /metrics (Prometheus). Import dashboards from marketplace/dashboards.
- Tracing:
  - Add OpenTelemetry tracing (HTTP server/client, FastAPI, httpx) for request chains.
- Logs:
  - Ensure structured logs and PII redaction guidelines; centralize in Cloud Logging.
- Health and tests:
  - Use scripts/odin-health.ps1 and tests/* for smoke; integrate into CI/CD.

## Deployment
- Cloud Run:
  - Min instances to reduce cold starts; set CPU/memory/timeout budgets.
  - Lock down ingress to internal; require auth; set max concurrency per workload.
- CI/CD:
  - Keep WIF GitHub Actions; tags trigger build/deploy. Pin base images and dependencies.

## Gaps to Plan For
- SSO for human users (admin/UI) if needed; current admin uses static token header.
- Strong multi-tenancy controls (policy + storage isolation).
- DLP/classification policy and content filters where required by compliance.
- End-to-end tracing out of the box (add Otel).

## Quick Toggle Map
- Proof enforcement: ODIN_ENFORCE_ROUTES, ODIN_ENFORCE_REQUIRE
- Response signing: ODIN_SIGN_ROUTES, ODIN_SIGN_EMBED, ODIN_SIGN_REQUIRE
- HTTP-sign enforcement: ODIN_HTTP_SIGN_ENFORCE_ROUTES
- Rate limits: ODIN_GATEWAY_RATE_LIMIT_QPS, ODIN_RELAY_RATE_LIMIT_QPS
- ID tokens (egress): ODIN_RELAY_ID_TOKEN, ODIN_BRIDGE_ID_TOKEN, ODIN_MESH_ID_TOKEN, ODIN_ID_TOKEN_AUDIENCE
- Admin: ODIN_ENABLE_ADMIN, ODIN_ADMIN_TOKEN
- JWKS/keys: ODIN_KEYSTORE_PATH or ODIN_KEYSTORE_JSON, JWKS_CACHE_TTL, ROTATION_GRACE_SEC
