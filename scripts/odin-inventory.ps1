# ODIN Repository Inventory (PowerShell 5.1)
param()

$ErrorActionPreference = 'Continue'

function Has-Cmd([string]$name) {
  return ($null -ne (Get-Command $name -ErrorAction SilentlyContinue))
}

function Run-Git($argsArray) {
  if (-not (Has-Cmd 'git')) { return '' }
  $out = & git @argsArray 2>&1
  if ($LASTEXITCODE -ne 0) { return '' }
  return ($out | Out-String).Trim()
}

function RelPath([string]$root, [string]$path) {
  try {
    $rp = Resolve-Path -LiteralPath $path -ErrorAction SilentlyContinue
    if ($rp) { return ($rp.Path.Substring($root.Length)).TrimStart('\\','/').Replace('\\','/') }
  } catch {}
  return $path.Replace('\\','/')
}

# Determine repo root
$root = ''
$gitRoot = Run-Git @('rev-parse','--show-toplevel')
if ($gitRoot -and $gitRoot -ne '') { $root = $gitRoot } else { $root = (Get-Location).Path }

# Prepare docs dir
$docsDir = Join-Path $root 'docs'
New-Item -ItemType Directory -Force -Path $docsDir | Out-Null
$inventoryPath = Join-Path $docsDir 'REPO_INVENTORY.md'

# Metadata
$branch = Run-Git @('rev-parse','--abbrev-ref','HEAD')
$commit = Run-Git @('rev-parse','HEAD')
$remote = Run-Git @('remote','get-url','origin')

# Top-level dirs with file counts
$topDirs = @()
try { $topDirs = Get-ChildItem -Path $root -Directory -Force -ErrorAction SilentlyContinue } catch {}
$dirLines = @()
foreach ($d in $topDirs) {
  $fcount = 0
  try { $fcount = (Get-ChildItem -Path $d.FullName -File -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object).Count } catch {}
  $dirLines += ('- ' + (RelPath $root $d.FullName) + '/ (' + ([string]$fcount) + ' files)')
}

# Workflows
$workflows = @()
$wfDir = Join-Path $root '.github/workflows'
if (Test-Path $wfDir) {
  try { $workflows = Get-ChildItem -Path $wfDir -File -Filter *.yml -ErrorAction SilentlyContinue } catch {}
}
$wfLines = @()
foreach ($w in $workflows) { $wfLines += ('- ' + (RelPath $root $w.FullName)) }

# Dockerfiles
$dockerFiles = @()
try {
  $allFiles = Get-ChildItem -Path $root -Recurse -File -Force -ErrorAction SilentlyContinue
  $dockerFiles = $allFiles | Where-Object { $_.Name -eq 'Dockerfile' -or $_.Name -like 'Dockerfile.*' }
} catch {}
$dockerLines = @()
foreach ($f in $dockerFiles) { $dockerLines += ('- ' + (RelPath $root $f.FullName)) }

# Key manifests
$reqFiles = @()
$pyprojFiles = @()
$pkgJsonFiles = @()
try {
  $reqFiles = Get-ChildItem -Path $root -Recurse -File -Filter requirements.txt -ErrorAction SilentlyContinue
  $pyprojFiles = Get-ChildItem -Path $root -Recurse -File -Filter pyproject.toml -ErrorAction SilentlyContinue
  $pkgJsonFiles = Get-ChildItem -Path $root -Recurse -File -Filter package.json -ErrorAction SilentlyContinue
} catch {}

$keyLines = @()
foreach ($f in $reqFiles) { $keyLines += ('- ' + (RelPath $root $f.FullName)) }
foreach ($f in $pyprojFiles) { $keyLines += ('- ' + (RelPath $root $f.FullName)) }
foreach ($f in $pkgJsonFiles) { $keyLines += ('- ' + (RelPath $root $f.FullName)) }

# apps/** and services/** directories (first-level)
$appsList = @()
$servicesList = @()
$appsDir = Join-Path $root 'apps'
$servicesDir = Join-Path $root 'services'
if (Test-Path $appsDir) {
  try { $appsList = Get-ChildItem -Path $appsDir -Directory -ErrorAction SilentlyContinue } catch {}
}
if (Test-Path $servicesDir) {
  try { $servicesList = Get-ChildItem -Path $servicesDir -Directory -ErrorAction SilentlyContinue } catch {}
}
$appsLines = @(); foreach ($d in $appsList) { $appsLines += ('- ' + (RelPath $root $d.FullName) + '/') }
$servicesLines = @(); foreach ($d in $servicesList) { $servicesLines += ('- ' + (RelPath $root $d.FullName) + '/') }

# Marketplace pack enumeration
$marketLines = @()
$marketDir = Join-Path $root 'marketplace'
if (Test-Path $marketDir) {
  # Markdown
  $mds = Get-ChildItem -Path $marketDir -Recurse -File -Filter *.md -ErrorAction SilentlyContinue
  foreach ($m in $mds) { $marketLines += ('- ' + (RelPath $root $m.FullName)) }
  # Helm chart
  $chartYaml = Get-ChildItem -Path $marketDir -Recurse -File -Filter Chart.yaml -ErrorAction SilentlyContinue
  foreach ($c in $chartYaml) { $marketLines += ('- ' + (RelPath $root $c.FullName)) }
  $valuesYaml = Get-ChildItem -Path $marketDir -Recurse -File -Filter values.yaml -ErrorAction SilentlyContinue
  foreach ($v in $valuesYaml) { $marketLines += ('- ' + (RelPath $root $v.FullName)) }
  $templates = Get-ChildItem -Path $marketDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '\\templates\\' -and $_.Extension -in '.yaml','.yml' }
  foreach ($t in $templates) { $marketLines += ('- ' + (RelPath $root $t.FullName)) }
  # Dashboards JSON
  $dash = Get-ChildItem -Path $marketDir -Recurse -File -Filter *.json -ErrorAction SilentlyContinue
  foreach ($j in $dash) { $marketLines += ('- ' + (RelPath $root $j.FullName)) }
}

# Detect code entrypoints and endpoints
$scanFiles = @()
try { $scanFiles = Get-ChildItem -Path $root -Recurse -File -Include *.py,*.ts,*.js -ErrorAction SilentlyContinue } catch {}

function Scan-Pattern([string]$pattern) {
  $lines = @()
  if ($scanFiles.Count -eq 0) { return $lines }
  try {
    $hits = Select-String -Path ($scanFiles | ForEach-Object { $_.FullName }) -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue
    $i = 0
    foreach ($h in $hits) {
      if ($i -ge 12) { break }
      $snippet = ($h.Line).Trim()
      $lines += ('- ' + (RelPath $root $h.Path) + ':' + ([string]$h.LineNumber) + ' — ' + $snippet)
      $i++
    }
  } catch {}
  return $lines
}

$entryLines = @()
$entryLines += (Scan-Pattern 'uvicorn')
$entryLines += (Scan-Pattern 'FastAPI(')

$endpointLines = @()
$endpointLines += (Scan-Pattern '/.well-known/odin/discovery.json')
$endpointLines += (Scan-Pattern '/metrics')
$endpointLines += (Scan-Pattern '/v1/envelope')
$endpointLines += (Scan-Pattern '/v1/translate')
$endpointLines += (Scan-Pattern '/v1/receipts/hops')
$endpointLines += (Scan-Pattern '/relay')

# Build markdown
$md = @()
$md += '# Repository Inventory'
$md += ''
$md += ('Root: ' + $root)
if ($branch -ne '') { $md += ('Branch: ' + $branch) }
if ($commit -ne '') { $md += ('Commit: ' + $commit) }
if ($remote -ne '') { $md += ('Remote: ' + $remote) }
$md += ''
$md += '## Top-level structure'
if ($dirLines.Count -gt 0) { $md += $dirLines } else { $md += '- (no directories found)' }
$md += ''
$md += '## Workflows'
if ($wfLines.Count -gt 0) { $md += $wfLines } else { $md += '- (no workflows found)' }
$md += ''
$md += '## Containers & Deployment (Dockerfiles)'
if ($dockerLines.Count -gt 0) { $md += $dockerLines } else { $md += '- (no Dockerfiles found)' }
$md += ''
$md += '## Key Manifests'
if ($keyLines.Count -gt 0) { $md += $keyLines } else { $md += '- (no manifests found)' }
$md += ''
$md += '## Code Entrypoints (detected)'
if ($entryLines.Count -gt 0) { $md += $entryLines } else { $md += '- (none detected)' }
$md += ''
$md += '## Endpoints (detected)'
if ($endpointLines.Count -gt 0) { $md += $endpointLines } else { $md += '- (none detected)' }
$md += ''
$md += '## Marketplace Pack'
if ($marketLines.Count -gt 0) { $md += $marketLines } else { $md += '- (no marketplace content found)' }
$md += ''
$md += ('Generated: ' + ([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')))

$md -join "`n" | Out-File -FilePath $inventoryPath -Encoding UTF8

Write-Host ('Inventory written: ' + $inventoryPath)
