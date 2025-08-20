# Deploy ODIN Gateway + Relay to Cloud Run

Set variables (defaults shown):
```powershell
$PROJECT_ID = $env:PROJECT_ID; if (-not $PROJECT_ID) { $PROJECT_ID = 'odin-producer' }
$REGION = $env:REGION; if (-not $REGION) { $REGION = 'us-central1' }
$AR_REPO = $env:AR_REPO; if (-not $AR_REPO) { $AR_REPO = 'odin' }
$IMAGE_TAG = $env:IMAGE_TAG; if (-not $IMAGE_TAG) { $IMAGE_TAG = 'v1.0.0' }
$AR_BASE = "$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO"
gcloud config set project $PROJECT_ID | Out-Null
```

Create service accounts (optional):
```powershell
gcloud iam service-accounts create gateway-run --display-name "Gateway Cloud Run SA" 2>$null
gcloud iam service-accounts create relay-run --display-name "Relay Cloud Run SA" 2>$null
```

Deploy odin-gateway:
```powershell
$G_IMG = "$AR_BASE/gateway:$IMAGE_TAG"
gcloud run deploy odin-gateway `
  --region $REGION `
  --image $G_IMG `
  --allow-unauthenticated `
  --min-instances 1 `
  --update-env-vars "ODIN_STORAGE=firestore,JWKS_CACHE_TTL=300,ROTATION_GRACE_SEC=600" `
  --update-secrets "ODIN_ADMIN_KEY=odin-admin-key:latest"
```

Deploy odin-relay:
```powershell
$R_IMG = "$AR_BASE/relay:$IMAGE_TAG"
gcloud run deploy odin-relay `
  --region $REGION `
  --image $R_IMG `
  --allow-unauthenticated `
  --min-instances 1 `
  --update-env-vars "ODIN_STORAGE=firestore,ODIN_RELAY_RATE_LIMIT_QPS=20"
```

After deploy, capture URLs:
```powershell
$gw = gcloud run services describe odin-gateway --region $REGION --format "value(status.url)"
$rl = gcloud run services describe odin-relay --region $REGION --format "value(status.url)"
"gateway: $gw"; "relay: $rl"
```
