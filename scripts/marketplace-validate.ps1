param(
  [string]$PROJECT_ID,
  [string]$REGION,
  [string]$AR_REPO,
  [string]$IMAGE_TAG
)

$ErrorActionPreference = 'Stop'

function Get-PythonPath {
  if (Test-Path ".venv\\Scripts\\python.exe") { return ".venv\\Scripts\\python.exe" }
  if (Get-Command python -ErrorAction SilentlyContinue) { return (Get-Command python).Source }
  if (Get-Command py -ErrorAction SilentlyContinue) { return (Get-Command py).Source }
  throw "Python interpreter not found. Install Python or create .venv."
}

function Invoke-Py {
  param(
    [Parameter(Mandatory=$true)][string]$Code,
    [string[]]$Args
  )
  $tmp = [System.IO.Path]::Combine($env:TEMP, "py_" + [System.Guid]::NewGuid().ToString('N') + ".py")
  Set-Content -Path $tmp -Value $Code -Encoding UTF8
  try {
    $py = Get-PythonPath
    Write-Host "CMD> $py $tmp $($Args -join ' ')"
    & $py $tmp @Args
    $exit = $LASTEXITCODE
    return $exit
  } finally {
    Remove-Item -Path $tmp -ErrorAction SilentlyContinue
  }
}

# Derived variables
$PROJECT_ID = if ($PROJECT_ID) { $PROJECT_ID } elseif ($env:PROJECT_ID) { $env:PROJECT_ID } else { 'odin-producer' }
$REGION = if ($REGION) { $REGION } elseif ($env:REGION) { $env:REGION } else { 'us-central1' }
$AR_REPO = if ($AR_REPO) { $AR_REPO } elseif ($env:AR_REPO) { $env:AR_REPO } else { 'odin' }
$IMAGE_TAG = if ($IMAGE_TAG) { $IMAGE_TAG } elseif ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { 'v1.0.0' }

$AR_BASE = "$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO"

Write-Host ("Inputs => PROJECT_ID={0} REGION={1} AR_REPO={2} IMAGE_TAG={3}" -f $PROJECT_ID,$REGION,$AR_REPO,$IMAGE_TAG)
Write-Host ("Derived => AR_BASE={0}" -f $AR_BASE)

Write-Host "`n== Validate marketplace YAML/JSON =="
$pyValidator = @'
import os, sys, json
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception as e:
    print("yaml library missing; run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

root = Path('marketplace')
if not root.exists():
    print('marketplace directory not found', file=sys.stderr)
    sys.exit(1)

errors = []
def is_template_text(txt: str) -> bool:
    return '{{' in txt and '}}' in txt

for p in root.rglob('*'):
    if p.is_file():
        rel = p.as_posix()
        if p.suffix.lower() in ('.yaml', '.yml'):
            txt = p.read_text(encoding='utf-8', errors='ignore')
            if 'templates/' in rel and is_template_text(txt):
                print(f'SKIP template: {rel}')
                continue
            try:
                yaml.safe_load(txt or '{}')
                print(f'YAML OK: {rel}')
            except Exception as e:
                print(f'YAML ERR: {rel} -> {e}')
                errors.append(rel)
        elif p.suffix.lower() == '.json':
            try:
                data = json.loads(p.read_text(encoding='utf-8', errors='ignore') or '{}')
                print(f'JSON OK: {rel} keys={list(data.keys())[:6]}')
            except Exception as e:
                print(f'JSON ERR: {rel} -> {e}')
                errors.append(rel)

print('SUMMARY: errors=' + str(len(errors)))
sys.exit(1 if errors else 0)
'@
$rc = Invoke-Py -Code $pyValidator
Write-Host "Validator exit=$rc"

Write-Host "`n== GitHub Actions run link (Release for tag v0.0.1) =="
$repoSlug = 'Maverick0351a/ODINAIMESH'
if (Get-Command gh -ErrorAction SilentlyContinue) {
  $url = "https://github.com/$repoSlug/actions/workflows/release.yml?query=tag%3Av0.0.1"
  Write-Host "CMD> gh --version"
  (gh --version) | Out-Host
  try {
    Write-Host "CMD> gh run list --workflow release.yml --json databaseId,headBranch,headSha,headTag,status,url --limit 20"
    $runs = gh run list --workflow release.yml --json databaseId,headBranch,headSha,headTag,status,url --limit 20 | ConvertFrom-Json
    $match = $runs | Where-Object { $_.headTag -eq 'v0.0.1' } | Select-Object -First 1
    if ($match -and $match.url) { Write-Host "Release run: $($match.url)" } else { Write-Host "No run found for tag v0.0.1. See: $url" }
  } catch {
    Write-Host "Failed to query gh runs. See: $url"
  }
} else {
  Write-Host "gh CLI not found. Visit: https://github.com/$repoSlug/actions/workflows/release.yml?query=tag%3Av0.0.1"
}

Write-Host "`n== Artifact Registry tags/digests (v0.0.1) =="
Write-Host "CMD> gcloud config set project $PROJECT_ID"
(gcloud config set project $PROJECT_ID --quiet) | Out-Host
foreach ($img in @('gateway','relay')) {
  $path = "$AR_BASE/$img"
  Write-Host "CMD> gcloud artifacts docker tags list $path --format=table(tag,digest,createTime) | findstr v0.0.1"
  try {
    $out = gcloud artifacts docker tags list $path --format="table(tag,digest,createTime)"
    ($out | Select-String -SimpleMatch 'v0.0.1') | ForEach-Object { $_.Line } | Out-Host
  } catch {
    Write-Host "Unable to query tags for $path"
  }
}

Write-Host "`n== Cloud Run service URLs (us-central1) =="
foreach ($svc in @('odin-gateway','odin-relay')) {
  try {
    $u = gcloud run services describe $svc --region $REGION --format="value(status.url)" 2>$null
    if ($u) { Write-Host "${svc}: ${u}" } else { Write-Host "${svc}: not found" }
  } catch { Write-Host "${svc}: describe failed" }
}

Write-Host "`n== Git tag check (v0.0.1) =="
Write-Host "CMD> git tag --list v0.0.1"
(git tag --list v0.0.1) | Out-Host
Write-Host "CMD> git ls-remote --tags origin v0.0.1"
$remote = (git ls-remote --tags origin v0.0.1) 2>$null
if ($remote) {
  Write-Host "Remote tag exists for v0.0.1"
} else {
  Write-Host "Remote tag NOT found. To create and push:"
  Write-Host "  git tag v0.0.1"
  Write-Host "  git push origin v0.0.1"
}

Write-Host "`nDone. Review output above."
