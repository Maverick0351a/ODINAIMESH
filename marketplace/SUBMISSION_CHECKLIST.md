# Marketplace Submission Checklist

- Producer project ownership: Confirm PROJECT_ID and billing enabled.
- Images in Artifact Registry: gateway:<TAG>, relay:<TAG> under `us-central1-docker.pkg.dev/<PROJECT_ID>/<AR_REPO>`.
- Deployment docs: `marketplace/CLOUDRUN.md`, `marketplace/README.md`.
- Observability: dashboards JSON in `marketplace/dashboards/`.
- Support contact: update `marketplace/README.md`.
- Terms/License: include `LICENSE` at repo root.
- Pricing: BYOL (initial). Usage-based telemetry optional later.
- Security posture: WIF, no static keys; SSRF protections on Relay.
- Test plan: run `scripts/odin-health.ps1` and smoke `scripts/run-tests.ps1`.
