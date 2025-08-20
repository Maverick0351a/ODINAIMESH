param(
  [switch]$Js,
  [switch]$Serve
)

Write-Host "== PYTEST =="
.\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Js) {
  Write-Host "== VITEST =="
  Push-Location packages\sdk
  npm test --silent
  $code = $LASTEXITCODE
  Pop-Location
  if ($code -ne 0) { exit $code }
}

if ($Serve) {
  Write-Host "== UVICORN =="
  $p = Start-Process -NoNewWindow -PassThru .\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","apps.gateway.api:app","--host","127.0.0.1","--port","7070"
  Start-Sleep -Seconds 1
  try {
    $h = Invoke-RestMethod http://127.0.0.1:7070/health -TimeoutSec 5
    Write-Host "HEALTH:" ($h | ConvertTo-Json -Compress)
  } catch {
    Write-Host "HEALTH: request failed"
    Stop-Process -Id $p.Id -Force
    exit 1
  }
  Stop-Process -Id $p.Id -Force
}
Write-Host "OK"
