Param(
  [string]$Project = $env:PROJECT_ID,
  [string]$AdminSecretName = "odin-admin-key",
  [string]$AdminValue = "",
  [string]$KeystoreSecretName = "odin-keystore",
  [string]$KeystoreJsonPath = ""
)
$ErrorActionPreference = "Stop"
if (-not $Project) { $Project = 'odin-producer' }
& gcloud config set project $Project | Out-Null

Write-Host "Ensuring Secret Manager secrets in $Project" -ForegroundColor Cyan

# Admin token
if ($AdminValue -and $AdminValue.Length -ge 12) {
  try { & gcloud secrets create $AdminSecretName --replication-policy=automatic 2>$null | Out-Null } catch {}
  $tmp = New-TemporaryFile
  try {
    Set-Content -Path $tmp -NoNewline -Value $AdminValue -Encoding ASCII
    & gcloud secrets versions add $AdminSecretName --data-file=$tmp | Out-Null
    Write-Host "Admin secret updated: $AdminSecretName" -ForegroundColor Green
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
} else {
  Write-Host "Skipped admin secret (provide -AdminValue with 12+ chars)" -ForegroundColor Yellow
}

# Keystore JSON
if ($KeystoreJsonPath -and (Test-Path $KeystoreJsonPath)) {
  try { & gcloud secrets create $KeystoreSecretName --replication-policy=automatic 2>$null | Out-Null } catch {}
  & gcloud secrets versions add $KeystoreSecretName --data-file=$KeystoreJsonPath | Out-Null
  Write-Host "Keystore secret updated: $KeystoreSecretName" -ForegroundColor Green
} else {
  Write-Host "Skipped keystore secret (provide -KeystoreJsonPath)" -ForegroundColor Yellow
}
