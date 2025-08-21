Param(
  [string]$Project = "odin-468307",
  [string]$Region = "us-central1",
  [string]$Service = "odin-gateway",
  [switch]$Unauthenticated,
  [string]$KeyFile,
  [string]$ServiceAccount,
  [int]$Concurrency = 80,
  [switch]$CpuAlwaysAllocated,
  [int]$MinInstances = 1,
  [int]$MaxInstances,
  [string]$KeystoreSecretName,
  [string]$KeystoreMountPath = "/var/secrets/odin/keystore.json",
  [string[]]$EnvVars
)
$ErrorActionPreference = "Stop"
Write-Host "Deploying to Cloud Run: project=$Project, service=$Service, region=$Region"

# Optional: authenticate with a service account key first
if ($KeyFile) {
  Write-Host "Activating service account with key file: $KeyFile"
  $acctArgs = @()
  if ($ServiceAccount) { $acctArgs += @("--account", $ServiceAccount) }
  & gcloud auth activate-service-account @acctArgs --key-file $KeyFile --project $Project
}

# Set project and ensure required APIs are enabled
& gcloud config set project $Project | Out-Null
& gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# Build & deploy directly from source using Cloud Build/Run
$authFlag = if ($Unauthenticated) { "--allow-unauthenticated" } else { "--no-allow-unauthenticated" }

# Assemble deploy args
$args = @("run","deploy",$Service,"--source",".","--region",$Region,$authFlag,"--port","8080")
if ($Concurrency) { $args += "--concurrency=$Concurrency" }
if ($CpuAlwaysAllocated) { $args += "--no-cpu-throttling" }
if ($MinInstances -ge 0) { $args += "--min-instances=$MinInstances" }
if ($MaxInstances) { $args += "--max-instances=$MaxInstances" }

# Secret mount for keystore
if ($KeystoreSecretName) {
  $args += "--mount=type=secret,source=$KeystoreSecretName,target=$KeystoreMountPath,mode=0440"
  # Ensure ODIN_KEYSTORE_PATH points to the mounted file if not explicitly set by user
  if (-not ($EnvVars | Where-Object { $_ -like "ODIN_KEYSTORE_PATH=*" })) {
    $EnvVars += "ODIN_KEYSTORE_PATH=$KeystoreMountPath"
  }
}

# Env vars
if ($EnvVars -and $EnvVars.Length -gt 0) {
  $joined = [string]::Join(",", $EnvVars)
  $args += "--set-env-vars=$joined"
}

& gcloud @args

# Show service URL
& gcloud run services describe $Service --region $Region --format "value(status.url)"
