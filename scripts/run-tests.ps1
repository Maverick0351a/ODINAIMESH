# Run pytest with optional URLs
param(
  [string]$GATEWAY_URL,
  [string]$RELAY_URL
)

$env:GATEWAY_URL = if ($GATEWAY_URL) { $GATEWAY_URL } else { $env:GATEWAY_URL }
$env:RELAY_URL   = if ($RELAY_URL)   { $RELAY_URL }   else { $env:RELAY_URL }

if (-not (Test-Path ".venv/Scripts/python.exe")) {
  Write-Host "Python venv not found at .venv. Skipping tests."
  exit 0
}

& .venv\Scripts\python.exe -m pip install -q pytest httpx
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
