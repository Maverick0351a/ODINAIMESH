param(
  [string]$PROJECT_ID = 'odin-producer',
  [string]$REGION = 'us-central1',
  [string]$AR_REPO = 'odin',
  [string]$TAG = 'v0.0.2',
  [int]$Attempts = 6,
  [int]$DelaySeconds = 10
)

$ErrorActionPreference = 'Stop'
$AR_BASE = "$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO"
Write-Host ("Using PROJECT_ID={0} REGION={1} AR_BASE={2} TAG={3}" -f $PROJECT_ID,$REGION,$AR_BASE,$TAG)

Write-Host "CMD> gcloud config set project $PROJECT_ID"
(gcloud config set project $PROJECT_ID --quiet) | Out-Host

for ($i=1; $i -le $Attempts; $i++) {
  Write-Host ("Attempt {0}/{1}" -f $i,$Attempts)
  foreach ($img in @('gateway','relay')) {
    $path = "$AR_BASE/$img"
    Write-Host "CMD> gcloud artifacts docker tags list $path --format=table(tag,digest,createTime) | findstr $TAG"
    try {
      $out = gcloud artifacts docker tags list $path --format="table(tag,digest,createTime)"
      ($out | Select-String -SimpleMatch $TAG) | ForEach-Object { $_.Line } | Out-Host
    } catch {
      Write-Host "Error querying tags for $path"
    }
  }
  Write-Host "CMD> gcloud run services describe odin-gateway --region $REGION --format=value(status.url)"
  try { (gcloud run services describe odin-gateway --region $REGION --format="value(status.url)" 2>$null) | Out-Host } catch { Write-Host 'odin-gateway: describe failed' }
  Write-Host "CMD> gcloud run services describe odin-relay --region $REGION --format=value(status.url)"
  try { (gcloud run services describe odin-relay --region $REGION --format="value(status.url)" 2>$null) | Out-Host } catch { Write-Host 'odin-relay: describe failed' }

  if ($i -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
}

Write-Host 'Done.'
