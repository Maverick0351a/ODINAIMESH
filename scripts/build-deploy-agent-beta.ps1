param(
  [string]$Project = "odin-468307",
  [string]$Region = "us-central1",
  [string]$Repo = "odin",
  [string]$Service = "agent-beta",
  [string]$GatewayJwksUrl = "https://odin-gateway-237788780100.us-central1.run.app/.well-known/odin/jwks.json",
  [switch]$SkipDeploy
)

$ErrorActionPreference = 'Stop'

# Validate gcloud CLI presence
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
  Write-Error "gcloud CLI is not installed or not on PATH. Install Google Cloud SDK and retry."
  exit 1
}

$DEPLOY = if ($SkipDeploy) { "false" } else { "true" }

Write-Host "Submitting Cloud Build for Agent Beta..." -ForegroundColor Cyan
Write-Host "  Project   : $Project"
Write-Host "  Region    : $Region"
Write-Host "  Repo      : $Repo"
Write-Host "  Service   : $Service"
Write-Host "  Deploy    : $DEPLOY"
if ($DEPLOY -eq 'true') { Write-Host "  Gateway JWKS URL: $GatewayJwksUrl" }

# Run Cloud Build
# Uses cloudbuild.agent-beta.yaml at repo root
$substitutions = "_REGION=$Region,_AR_REPO=$Repo,_SERVICE=$Service,_DEPLOY=$DEPLOY,_GATEWAY_JWKS_URL=$GatewayJwksUrl"

# Note: PowerShell uses backticks for line continuations
& gcloud builds submit `
  --project $Project `
  --config cloudbuild.agent-beta.yaml `
  --substitutions $substitutions

if ($LASTEXITCODE -ne 0) {
  Write-Error "Cloud Build failed with exit code $LASTEXITCODE"
  exit $LASTEXITCODE
}

Write-Host "Cloud Build completed." -ForegroundColor Green
if ($DEPLOY -eq 'true') {
  Write-Host "Deployment triggered by Cloud Build. Check Cloud Run service: $Service in region $Region." -ForegroundColor Green
} else {
  Write-Host "Deployment skipped. Image pushed to Artifact Registry." -ForegroundColor Yellow
}
