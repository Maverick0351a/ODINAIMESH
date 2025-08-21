param(
  [string]$Project = 'odin-producer',
  [string]$Repo = 'odin',
  [string]$Tag = 'v0.0.1',
  [string]$Dockerfile = 'Dockerfile'
)

$ErrorActionPreference = 'Stop'

$Img = "us-central1-docker.pkg.dev/$Project/$Repo/gateway:$Tag"
Write-Host ("Building image: " + $Img)

# Ensure AR docker auth configured by caller

& docker build -t $Img -f $Dockerfile .
if ($LASTEXITCODE -ne 0) { Write-Error "docker build failed"; exit $LASTEXITCODE }

& docker push $Img
if ($LASTEXITCODE -ne 0) { Write-Error "docker push failed"; exit $LASTEXITCODE }

Write-Host ("Pushed: " + $Img)
