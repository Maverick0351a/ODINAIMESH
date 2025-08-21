param(
  [string]$Project = 'odin-producer',
  [string]$Region = 'us-central1',
  [string]$Image = 'us-central1-docker.pkg.dev/odin-producer/odin/gateway:v0.0.1'
)

$ErrorActionPreference = 'Stop'

# Ensure project context
& gcloud @('config','set','project',$Project) | Write-Output

# Deploy odin-gateway with array-style args to avoid quoting issues
$args = @(
  'run','deploy','odin-gateway',
  '--project',$Project,
  '--region',$Region,
  '--image',$Image,
  '--platform','managed',
  '--allow-unauthenticated',
  '--min-instances','1',
  '--update-env-vars','ODIN_STORAGE=firestore,JWKS_CACHE_TTL=300,ROTATION_GRACE_SEC=600',
  '--quiet'
)

& gcloud @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
