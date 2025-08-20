# Deploy to Google Cloud Run

Prereqs
- gcloud CLI authenticated to your org/project
- Project has Cloud Run, Artifact Registry, Secret Manager enabled
- Artifact Registry repo `odin` in `us-central1`

Images
- gateway: us-central1-docker.pkg.dev/odin-producer/odin/gateway:v1.0.0
- relay: us-central1-docker.pkg.dev/odin-producer/odin/relay:v1.0.0

Steps
1) Create service accounts
- gateway-run and relay-run
2) Create a GCS bucket for storage
- example: gs://odin-producer-mesh-data
3) Grant IAM
- storage.objectAdmin to gateway-run on the bucket
- storage.objectViewer to relay-run on the bucket (optional)
4) Deploy services
- Cloud Run (managed), port 8080, min 0, max 5-10
- Set env vars from marketplace/MARKETPLACE.md
5) Secure invoker
- Prefer authenticated invoker; grant specific users/Workload Identity pool service account.
6) Domain mapping (optional)
- Map `api.your-domain` -> gateway service, managed TLS.

Secret Manager
- STRIPE_SECRET_KEY and OPENAI_API_KEY are recommended to be provided via Cloud Run Secret environment variables.

Health
- GET /health -> 200 JSON
- GET /metrics -> Prometheus format
