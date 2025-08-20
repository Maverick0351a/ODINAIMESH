# ODIN Protocol — Marketplace Package

ODIN provides a Gateway (FastAPI) and Relay (FastAPI) to make AI-to-AI traffic typed, signed, translated, and auditable. This package targets Google Cloud Run deployments with observability and least-privilege CI via Workload Identity Federation (WIF).

## Components
- Gateway: discovery `/.well-known/odin/discovery.json`, JWKS, translate, verify, receipts, optional `/v1/envelope`, `/metrics`.
- Relay: hardened `POST /relay` (rate limiting, SSRF guard, retries), optional ID token injection, `/metrics`.

## Deploy (Cloud Run)
See `marketplace/CLOUDRUN.md` for step-by-step deployment. Images are expected in Artifact Registry under `us-central1-docker.pkg.dev/<PROJECT_ID>/<AR_REPO>/{gateway,relay}:<TAG>`.
- Helper scripts:
	- `scripts/secrets-bootstrap.ps1` – create/update Secret Manager entries for ODIN_ADMIN_KEY and ODIN_KEYSTORE_JSON.
	- `scripts/deploy-cloudrun-secure.ps1` – deploy gateway/relay with no public access, tracing enabled, rate limits set.
- Perimeter hardening: see `marketplace/CLOUD_ARMOR.md` for a quick WAF setup.

## Observability
- Prometheus metrics at `/metrics`.
- Sample Cloud Monitoring dashboards in `marketplace/dashboards/`.

## Security
- GitHub Actions → Google Cloud via WIF (OIDC), no static keys in repo.
- Relay SSRF protections enabled by default.

## Support
- Issues: GitHub Issues
- Email: support@example.com
