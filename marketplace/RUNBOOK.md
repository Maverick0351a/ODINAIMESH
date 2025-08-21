# Runbook – ODIN Gateway + Relay

## Health checks
- Metrics: GET /metrics (Prometheus) – used for probes and scraping.
- Gateway: GET /health (expects {"ok": true}). Optional: /v1/envelope for end-to-end check.

## Common issues
- SSRF protections: relay enforces safe outbound patterns; validate HEL policy for allowed domains.
- Signature mismatch: ensure clients sign correctly; check odin_httpsig_verifications_total and review policy flags.
- Rate limit: adjust ODIN_RELAY_RATE_LIMIT_QPS and upstream limits; verify 429s.
- Storage/ledger failures: for Firestore or GCS backends, confirm IAM and existence; monitor odin_receipt_write_failures_total.

## Receipts storage options
- Firestore (recommended for low-latency ledger). Configure ODIN_STORAGE=firestore and collection name.
- GCS (bulk receipts). Configure bucket, prefix, and lifecycle policies.

## JWKS rotation
- JWKS_CACHE_TTL sets cache TTL, ROTATION_GRACE_SEC allows overlap.
- Rotate keys by publishing new JWKS; verify /.well-known/odin/jwks.

## Dynamic reload
- HEL policy URI is watched; enable reloads via env if applicable. Use admin key for sensitive operations.

## Rollback steps
1. Identify last known good ${IMAGE_TAG} in ${AR_BASE}.
2. Redeploy odin-gateway and odin-relay with that tag.
3. Validate /metrics and /health endpoints post-rollback.
