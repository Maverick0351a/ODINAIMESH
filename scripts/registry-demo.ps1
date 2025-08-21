param(
  [switch]$Keep
)

# Disable enforcement for envelope bootstrap
$env:ODIN_ENFORCE_ROUTES = ""

# Start gateway
$p = Start-Process -NoNewWindow -PassThru .\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","apps.gateway.api:app","--host","127.0.0.1","--port","7070"

# Wait for readiness
$ok = $false
for ($i=0; $i -lt 40; $i++) {
  try {
    $h = Invoke-RestMethod http://127.0.0.1:7070/health -TimeoutSec 2
    if ($h.ok) { $ok = $true; break }
  } catch {}
  Start-Sleep -Milliseconds 250
}
if (-not $ok) {
  Write-Error "Gateway failed to start"
  if ($p) { Stop-Process -Id $p.Id -Force }
  exit 1
}
Write-Host ("HEALTH: " + ($h | ConvertTo-Json -Compress))

# Advertisement
$ad = [ordered]@{
  intent = "odin.service.advertise"
  service = "agent_beta"
  version = "v1"
  base_url = "http://127.0.0.1:9090"
  sft = @("beta@v1")
  ttl_s = 3600
}
$adJson = $ad | ConvertTo-Json -Compress -Depth 8

# Envelope
$envResp = Invoke-RestMethod -Uri http://127.0.0.1:7070/v1/envelope -Method Post -ContentType 'application/json' -Body $adJson
if (-not $envResp.proof) {
  Write-Error "Envelope response missing proof"
  if ($p) { Stop-Process -Id $p.Id -Force }
  exit 1
}
$envProof = $envResp.proof
Write-Host ("ENVELOPE-KID: " + $envProof.kid)

# Fetch JWKS and attach inline to the proof so registry verification can resolve the key
$jwks = Invoke-RestMethod -Uri http://127.0.0.1:7070/.well-known/odin/jwks.json -Method Get
if ($null -eq $jwks.keys -or $jwks.keys.Count -eq 0) {
  Write-Error "JWKS is empty or missing 'keys' array"
  if ($p) { Stop-Process -Id $p.Id -Force }
  exit 1
}
$envProof | Add-Member -NotePropertyName jwks_inline -NotePropertyValue $jwks -Force

# Register
$bodyObj = @{ payload = $ad; proof = $envProof }
$regResp = Invoke-RestMethod -Uri http://127.0.0.1:7070/v1/registry/register -Method Post -ContentType 'application/json' -Body ($bodyObj | ConvertTo-Json -Compress -Depth 8)
Write-Host ("REGISTER-ID: " + $regResp.id)

# List
$listResp = Invoke-RestMethod -Uri "http://127.0.0.1:7070/v1/registry/services?service=agent_beta" -Method Get
Write-Host ("LIST-COUNT: " + $listResp.count)
if ($listResp.services.Count -gt 0) { Write-Host ("LIST-FIRST-ID: " + ($listResp.services[0].id)) }

# Optional keep running
if (-not $Keep -and $p) {
  Stop-Process -Id $p.Id -Force
}
