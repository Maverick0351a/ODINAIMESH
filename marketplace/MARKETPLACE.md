# ODIN Producer Pack

Short description: ODIN Gateway and Relay provide secure, observable, and scalable endpoints for AI task routing and relay. Deployable on Cloud Run, with an optional Helm chart for GKE.

## Long description
The ODIN Producer Pack contains two services:
- odin-gateway: A FastAPI service fronting ODIN task ingress/egress with built-in SSRF protections, request signing, dynamic policy reloads (HEL), and Prometheus metrics.
- odin-relay: A lightweight relay for outbound mesh hops with rate limiting and Prometheus metrics.

Supported deployments:
- Google Cloud Run (reference commands included).
- Kubernetes via Helm (templates included; compatible with GKE Autopilot or Standard).

Images are published to Artifact Registry, parameterized by:
- PROJECT_ID (default: odin-producer)
- REGION (default: us-central1)
- AR_REPO (default: odin)
- IMAGE_TAG (default: v1.0.0)

Derived variables used across this packet:
- AR_BASE = ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}
- IMAGE_TAG = ${IMAGE_TAG}

## Architecture
- Control plane: Cloud Run revision per service, minimum 1 instance for low-latency cold-starts.
- Data plane: HTTP/JSON; Prometheus /metrics endpoint; optional Managed Prometheus on GKE or Cloud Run.
- Optional deployment via Helm chart for GKE clusters.

## Security
- SSRF guard: egress restricted in production via VPC egress controls; gateway validates destinations and schemas.
- HEL policy: runtime policy URI is configurable; supports dynamic reloads and rotation.
- Receipts: signed receipts emitted for traceability; storage backends include Firestore or GCS (see runbook).
- Auth: administrative endpoints protected by an ODIN_ADMIN_KEY injected via Secret Manager or Kubernetes Secret.

## Observability
- /metrics (Prometheus exposition) on both services.
- Prebuilt Cloud Monitoring dashboard JSON at `marketplace/dashboards/odin-cloud-monitoring.json`.
- Key SLO indicators:
  - Gateway HTTP P95 latency.
  - Relay HTTP P95 latency.
  - ODIN hops emitted (prometheus odin_hops_total).
  - 5xx error rate.

## Pricing
- BYOL (Bring Your Own License) for now.
- Roadmap: usage-based pricing via metered billing integration.

## Support
- Contact: TravisJohnson@odinprotocol.dev
- Business hours: Mon–Fri 9am–6pm PT.

## Submission checklist
- [x] Cloud Run deployment commands validated.
- [x] Helm chart renders and includes ServiceMonitor manifests.
- [x] Dashboard JSON loads.
- [x] Security notes included (SSRF guard, HEL policy, receipts).
- [x] SLA and Runbook provided.
