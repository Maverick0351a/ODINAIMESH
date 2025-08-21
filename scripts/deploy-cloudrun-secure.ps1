Param(
  [string]$Project = $env:PROJECT_ID,
  [string]$Region = $env:REGION,
  [string]$Repo = $env:AR_REPO,
  [string]$Tag = $env:IMAGE_TAG,
  [int]$MinInstances = 1,
  [int]$GatewayQps = 10,
  [int]$RelayQps = 20,
  [string]$AdminSecret = "odin-admin-key",
  [string]$KeystoreSecret = "odin-keystore"
)
$ErrorActionPreference = "Stop"
if (-not $Project) { $Project = 'odin-producer' }
if (-not $Region) { $Region = 'us-central1' }
if (-not $Repo) { $Repo = 'odin' }
if (-not $Tag) { $Tag = 'v1.0.0' }
$AR = "$Region-docker.pkg.dev/$Project/$Repo"

& gcloud config set project $Project | Out-Null
Write-Host "Deploying odin-gateway and odin-relay to $Project/$Region with authenticated invokers" -ForegroundColor Cyan

# Gateway
$G_IMG = "$AR/gateway:$Tag"
& gcloud run deploy odin-gateway `
  --region $Region `
  --image $G_IMG `
  --no-allow-unauthenticated `
  --min-instances $MinInstances `
  --set-env-vars "ODIN_STORAGE=firestore,JWKS_CACHE_TTL=300,ROTATION_GRACE_SEC=600,ODIN_GATEWAY_RATE_LIMIT_QPS=$GatewayQps,ODIN_OTEL=1,ODIN_OTEL_EXPORTER=gcp" `
  --update-secrets "ODIN_ADMIN_KEY=$AdminSecret:latest,ODIN_KEYSTORE_JSON=$KeystoreSecret:latest"

# Relay
$R_IMG = "$AR/relay:$Tag"
& gcloud run deploy odin-relay `
  --region $Region `
  --image $R_IMG `
  --no-allow-unauthenticated `
  --min-instances $MinInstances `
  --set-env-vars "ODIN_STORAGE=firestore,ODIN_RELAY_RATE_LIMIT_QPS=$RelayQps,ODIN_OTEL=1,ODIN_OTEL_EXPORTER=gcp"

$gw = & gcloud run services describe odin-gateway --region $Region --format "value(status.url)"
$rl = & gcloud run services describe odin-relay --region $Region --format "value(status.url)"
Write-Host "gateway: $gw" -ForegroundColor Green
Write-Host "relay:   $rl" -ForegroundColor Green
