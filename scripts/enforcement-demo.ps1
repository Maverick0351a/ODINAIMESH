param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 7070
)

$ErrorActionPreference = 'Stop'

# Ensure policy file exists
$newPolicy = '{
  "allow_kids": ["env:*", "*"],
  "deny_kids": ["bad*"],
  "allowed_jwks_hosts": ["localhost", "127.0.0.1", "*.yourcompany.com"]
}'
$policyPath = Join-Path -Path (Resolve-Path .).Path -ChildPath 'config/hel_policy.json'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $policyPath) | Out-Null
if (-not (Test-Path $policyPath)) { $newPolicy | Set-Content -Encoding UTF8 $policyPath }

# Env
$env:ODIN_ENFORCE_ROUTES = "/v1/envelope,/v1/relay,/v1/secured"
$env:ODIN_HEL_POLICY_PATH = $policyPath

function Start-UvicornStrict($require) {
  $env:ODIN_ENFORCE_REQUIRE = "$require"
  # Kill any uvicorn first
  Get-Process -Name uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 1
  Start-Process -FilePath .\.venv\Scripts\uvicorn.exe -ArgumentList "apps.gateway.api:app","--host","$Host","--port","$Port"
  # Wait for health
  $healthUrl = "http://$Host:$Port/health"
  for ($i=0; $i -lt 20; $i++) {
    try {
      $h = Invoke-RestMethod -Uri $healthUrl -UseBasicParsing
      if ($h.ok) { return }
    } catch {}
    Start-Sleep -Milliseconds 300
  }
  throw "Gateway did not become healthy on $healthUrl"
}

function Invoke-StrictMissingProofCheck {
  $url = "http://$Host:$Port/v1/envelope"
  try {
    $bad = @{ payload = @{ hello = "world" } } | ConvertTo-Json -Compress
    Invoke-WebRequest -Uri $url -Method Post -ContentType 'application/json' -Body $bad -ErrorAction Stop | Out-Null
    Write-Output "Unexpected success posting without proof"
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Output "Strict missing-proof status: $code"
  }
}

function Get-EnvelopeSoft() {
  $url = "http://$Host:$Port/v1/envelope"
  $payload = @{ hello = "world" } | ConvertTo-Json -Compress
  # Use Invoke-WebRequest to keep raw JSON content
  $resp = Invoke-WebRequest -Uri $url -Method Post -ContentType 'application/json' -Body $payload
  $json = $resp.Content
  New-Item -ItemType Directory -Force -Path .\tmp | Out-Null
  $out = ".\tmp\env_bootstrap.json"
  $json | Set-Content -Encoding UTF8 $out
  return $out
}

function PostEnvelopeStrict($envFile) {
  $url = "http://$Host:$Port/v1/envelope"
  $body = Get-Content $envFile -Raw
  $resp = Invoke-WebRequest -Uri $url -Method Post -ContentType 'application/json' -Body $body
  return $resp.StatusCode
}

Write-Output "== Strict mode (require proof) =="
Start-UvicornStrict -require 1
Invoke-StrictMissingProofCheck

Write-Output "== Soft mode (bootstrap envelope) =="
Start-UvicornStrict -require 0
$envPath = Get-EnvelopeSoft
Write-Output "Saved envelope: $envPath"

Write-Output "== Strict mode (verify envelope) =="
Start-UvicornStrict -require 1
$status = PostEnvelopeStrict -envFile $envPath
Write-Output "Strict valid envelope status: $status"
