Param(
  [string]$Project = "odin-468307",
  [string]$Region = "us-central1",
  [string]$Repo = "odin",
  [string]$ImageName = "odin-gateway",
  [string]$Tag = "latest",
  [string]$Context = "."
)
$ErrorActionPreference = "Stop"

$RegistryHost = "$Region-docker.pkg.dev"
$Image = "$RegistryHost/$Project/$Repo/$ImageName"
$FullTag = "${Image}:$Tag"

Write-Host "Building image: $FullTag (context: $Context)"

# Configure Docker to use gcloud credential helper for Artifact Registry
& gcloud auth configure-docker $RegistryHost --quiet

# Build
& docker build -t $FullTag $Context

# Push
Write-Host "Pushing image: $FullTag"
& docker push $FullTag

Write-Host "Pushed: $FullTag"
