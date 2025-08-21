$ErrorActionPreference = "Stop"
Push-Location packages/sdk
try {
  if (Test-Path package-lock.json) { npm ci --silent } else { npm install --silent }
  npm test --silent
} finally {
  Pop-Location
}
