param(
  [string]$GatewayUrl = "http://127.0.0.1:7070",
  [string]$BetaUrl    = "http://127.0.0.1:9090/task",
  [switch]$StartServices = $true,
  [switch]$EnableHel = $true
)

trap { Write-Error $_; if ($gwProc) { try { Stop-Process -Id $gwProc.Id -Force } catch {} }; if ($betaProc) { try { Stop-Process -Id $betaProc.Id -Force } catch {} }; exit 1 }

$ErrorActionPreference = "Stop"

# Env for the Python demo
$env:ODIN_GATEWAY_URL = $GatewayUrl
$env:AGENT_BETA_URL   = $BetaUrl
$env:ODIN_SFT_MAPS_DIR = "config/sft_maps"

# Optional: enable HEL policy enforcement so the denied intent demo is effective
if ($EnableHel) {
  # Enforce on translate and (future) bridge; do NOT include /v1/envelope
  $env:ODIN_ENFORCE_ROUTES = "/v1/translate,/v1/bridge"
  $env:ODIN_HEL_POLICY_PATH = "config/hel.policy.example.json"
  $env:ODIN_ENFORCE_REQUIRE = "1"
}

Write-Host "GATEWAY=$($env:ODIN_GATEWAY_URL)  BETA=$($env:AGENT_BETA_URL)" -ForegroundColor Cyan

function Wait-Healthy($url, $name) {
  for ($i=0; $i -lt 30; $i++) {
    try {
      $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { return }
    } catch {}
    Start-Sleep -Milliseconds 300
  }
  throw "Timed out waiting for $name at $url"
}

if ($StartServices) {
  # Start Agent Beta
  $betaProc = Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList "apps.agent_beta.api:app","--host","127.0.0.1","--port","9090" -PassThru -WindowStyle Hidden
  Write-Host "Started Agent Beta (PID=$($betaProc.Id))" -ForegroundColor DarkGray
  # Start Gateway
  $gwProc = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","apps.gateway.api:app","--host","127.0.0.1","--port","7070" -PassThru -WindowStyle Hidden
  Write-Host "Started Gateway (PID=$($gwProc.Id))" -ForegroundColor DarkGray

  # Wait for health
  Wait-Healthy "$($GatewayUrl)/health" "Gateway"
  Wait-Healthy ( ($BetaUrl -replace '/task$','') + "/health") "Agent Beta"
}

try {
  .\.venv\Scripts\python.exe scripts\demo_agents_roundtrip.py
} finally {
  if ($StartServices) {
    if ($gwProc) { try { Stop-Process -Id $gwProc.Id -Force } catch {} }
    if ($betaProc) { try { Stop-Process -Id $betaProc.Id -Force } catch {} }
  }
}
