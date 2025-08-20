# ODIN Protocol Health Check (PowerShell 5.1 compatible)
param(
  [string]$PROJECT_ID,
  [string]$REGION,
  [string]$GATEWAY_SERVICE,
  [string]$RELAY_SERVICE,
  [string]$AR_REPO,
  [string]$TEST_TAG,
  [string]$ADMIN_KEY
)

$ErrorActionPreference = 'Continue'

function Get-Default($val, $fallback) { if ($null -ne $val -and $val -ne '') { return $val } else { return $fallback } }

$PROJECT_ID     = Get-Default $PROJECT_ID     (Get-Default $env:PROJECT_ID     'odin-producer')
$REGION         = Get-Default $REGION         (Get-Default $env:REGION         'us-central1')
$GATEWAY_SERVICE= Get-Default $GATEWAY_SERVICE(Get-Default $env:GATEWAY_SERVICE 'odin-gateway')
$RELAY_SERVICE  = Get-Default $RELAY_SERVICE  (Get-Default $env:RELAY_SERVICE   'odin-relay')
$AR_REPO        = Get-Default $AR_REPO        (Get-Default $env:AR_REPO        'odin')
$TEST_TAG       = Get-Default $TEST_TAG       (Get-Default $env:TEST_TAG       'v0.0.1')
$ADMIN_KEY      = Get-Default $ADMIN_KEY      (Get-Default $env:ADMIN_KEY      '')

$RunTs = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
$Root = (Get-Location).Path
$DocsDir = Join-Path $Root 'docs'
New-Item -ItemType Directory -Path $DocsDir -Force | Out-Null
$Appendix = Join-Path $DocsDir 'STATUS_README.appendix.txt'
$StatusMd = Join-Path $DocsDir 'STATUS_README.md'

function Append-Block([string]$Title, [string]$Content) {
  $line = ('# ' + $Title)
  ($line + "`n" + $Content + "`n`n") | Out-File -FilePath $Appendix -Encoding UTF8 -Append
}

function Mark([bool]$ok) { if ($ok) { return '✅' } else { return '❌' } }

function Get-Text([string]$url, [hashtable]$headers) {
  if (-not $headers) { $headers = @{} }
  try {
    $resp = Invoke-WebRequest -Uri $url -Method GET -Headers $headers -UseBasicParsing -TimeoutSec 30
    return [PSCustomObject]@{
      ok = $true; status = [int]$resp.StatusCode; text = $resp.Content; headers = $resp.Headers
    }
  } catch {
    $msg = $_ | Out-String; $status = 0
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $status = [int]$_.Exception.Response.StatusCode }
    return [PSCustomObject]@{ ok = $false; status = $status; text = $msg; headers = @{} }
  }
}

function Invoke-JsonPost([string]$url, $obj, [hashtable]$headers) {
  if (-not $headers) { $headers = @{} }
  $json = ''
  try { $json = $obj | ConvertTo-Json -Depth 12 } catch { $json = '' }
  $allHeaders = @{}
  foreach ($k in $headers.Keys) { $allHeaders[$k] = $headers[$k] }
  $allHeaders['Content-Type'] = 'application/json'
  try {
    $resp = Invoke-WebRequest -Uri $url -Method POST -Headers $allHeaders -Body $json -UseBasicParsing -TimeoutSec 60
    $bodyText = $resp.Content
    $parsed = $null; try { $parsed = $bodyText | ConvertFrom-Json } catch { $parsed = $null }
    return [PSCustomObject]@{ ok = $true; status = [int]$resp.StatusCode; text = $bodyText; headers = $resp.Headers; json = $parsed }
  } catch {
    $status = 0; $body = ''
    if ($_.Exception.Response) {
      try { $status = [int]$_.Exception.Response.StatusCode } catch {}
      try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $body = $sr.ReadToEnd() } catch { $body = ($_.Exception.Message) }
    } else { $body = ($_.Exception.Message) }
    $parsed = $null; try { $parsed = $body | ConvertFrom-Json } catch { $parsed = $null }
    return [PSCustomObject]@{ ok = $false; status = $status; text = $body; headers = @{}; json = $parsed }
  }
}

function Get-RunUrl([string]$service, [string]$region) {
  $fmt = 'value(status.url)'
  $cmdOut = & gcloud run services describe $service --region $region --format=$fmt 2>&1
  if ($LASTEXITCODE -ne 0) { return '' }
  return ($cmdOut | Out-String).Trim()
}

# ===== Part B: CI/CD & artifacts =====
$ci = [PSCustomObject]@{
  Project = $PROJECT_ID
  Region = $REGION
  GatewayImage = "us-central1-docker.pkg.dev/$PROJECT_ID/$AR_REPO/gateway"
  RelayImage   = "us-central1-docker.pkg.dev/$PROJECT_ID/$AR_REPO/relay"
  TestTag      = $TEST_TAG
  GatewayTagDigest = ''
  RelayTagDigest = ''
  GhRunStatus = ''
  GhRunConclusion = ''
  GhRunUrl = ''
}

$gcloudOk = $true
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) { $gcloudOk = $false; Append-Block 'ERROR' 'gcloud CLI not found in PATH.' }

if ($gcloudOk) {
  $setProjOut = & gcloud config set project $PROJECT_ID 2>&1
  Append-Block 'gcloud config set project' ($setProjOut | Out-String)

  $gwTagsRaw = & gcloud artifacts docker tags list $ci.GatewayImage --format json 2>&1
  $gwTags = $null; try { $gwTags = $gwTagsRaw | ConvertFrom-Json } catch {}
  Append-Block 'AR: gateway tags (raw)' ($gwTagsRaw | Out-String)

  $rlTagsRaw = & gcloud artifacts docker tags list $ci.RelayImage --format json 2>&1
  $rlTags = $null; try { $rlTags = $rlTagsRaw | ConvertFrom-Json } catch {}
  Append-Block 'AR: relay tags (raw)' ($rlTagsRaw | Out-String)

  if ($gwTags) { $m=$gwTags | Where-Object { $_.tag -eq $TEST_TAG } | Select-Object -First 1; if ($m) { $ci.GatewayTagDigest = $m.digest } }
  if ($rlTags) { $m=$rlTags | Where-Object { $_.tag -eq $TEST_TAG } | Select-Object -First 1; if ($m) { $ci.RelayTagDigest = $m.digest } }
}

# Optional GH info
$ghPresent = ($null -ne (Get-Command gh -ErrorAction SilentlyContinue))
if ($ghPresent) {
  try {
    $runListRaw = & gh run list --workflow release.yml --json databaseId,headBranch,headRef,displayTitle,status,conclusion,htmlUrl --limit 50 2>&1
    Append-Block 'gh run list (raw)' ($runListRaw | Out-String)
    $runs = $null; try { $runs = $runListRaw | ConvertFrom-Json } catch { $runs = $null }
    $run = $null
    if ($runs) { $run = ($runs | Where-Object { ($_.headRef -and $_.headRef -like ('refs/tags/' + $TEST_TAG)) -or ($_.displayTitle -like ('*' + $TEST_TAG + '*')) -or ($_.headBranch -eq $TEST_TAG) } | Select-Object -First 1) }
    if (-not $run -and $runs) { $run = $runs | Select-Object -First 1 }
    if ($run) {
      $ci.GhRunStatus = '' + $run.status
      $ci.GhRunConclusion = '' + $run.conclusion
      $ci.GhRunUrl = '' + $run.htmlUrl
      $logRaw = & gh run view $run.databaseId --log 2>&1
      $keyLines = ($logRaw | Select-String -Pattern 'google-github-actions/auth|configure-docker|docker push|gcloud run deploy' -AllMatches) | ForEach-Object { $_.Line }
      $sample = ($keyLines | Select-Object -First 30) -join "`n"
      Append-Block 'gh run view (filtered logs)' $sample
    } else {
      $ci.GhRunUrl = "https://github.com/Maverick0351a/ODINAIMESH/actions/workflows/release.yml?query=tag%3A$TEST_TAG"
    }
  } catch { Append-Block 'gh error' ($_ | Out-String) }
} else {
  $ci.GhRunUrl = "https://github.com/Maverick0351a/ODINAIMESH/actions/workflows/release.yml?query=tag%3A$TEST_TAG"
}

# ===== Part C: Runtime health =====
$GATEWAY_URL = ''; $RELAY_URL = ''
if ($gcloudOk) {
  $GATEWAY_URL = Get-RunUrl -service $GATEWAY_SERVICE -region $REGION
  $RELAY_URL   = Get-RunUrl -service $RELAY_SERVICE -region $REGION
}
Append-Block 'Cloud Run URL (gateway)' $GATEWAY_URL
Append-Block 'Cloud Run URL (relay)' $RELAY_URL

$checks = @{}
$codes  = @{}
$metricsNames = @()

# Metrics
$gwMetrics = $null; $rlMetrics = $null
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $gwMetrics = Get-Text -url ($GATEWAY_URL.TrimEnd('/') + '/metrics') -headers @{}
  $codes['gateway_metrics'] = $gwMetrics.status
  $checks['gateway_metrics'] = $gwMetrics.ok -and ($gwMetrics.status -ge 200 -and $gwMetrics.status -lt 400)
  Append-Block 'Gateway /metrics (first 10 lines)' ((($gwMetrics.text -split "`n") | Select-Object -First 10) -join "`n")
  if ($gwMetrics.ok) { $metricsNames += (($gwMetrics.text -split "`n") | Where-Object { $_ -match '^[a-zA-Z_]+\{' -or $_ -match '^[a-zA-Z_]+' } | Select-Object -First 10) }
} else { $checks['gateway_metrics'] = $false; $codes['gateway_metrics'] = 0 }

if ($RELAY_URL -and $RELAY_URL -ne '') {
  $rlMetrics = Get-Text -url ($RELAY_URL.TrimEnd('/') + '/metrics') -headers @{}
  $codes['relay_metrics'] = $rlMetrics.status
  $checks['relay_metrics'] = $rlMetrics.ok -and ($rlMetrics.status -ge 200 -and $rlMetrics.status -lt 400)
  Append-Block 'Relay /metrics (first 10 lines)' ((($rlMetrics.text -split "`n") | Select-Object -First 10) -join "`n")
} else { $checks['relay_metrics'] = $false; $codes['relay_metrics'] = 0 }

# Envelope
$traceId = ''
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $envResp = Invoke-JsonPost -url ($GATEWAY_URL.TrimEnd('/') + '/v1/envelope') -obj @{ payload = @{ hello = 'world' } } -headers @{}
  $checks['envelope'] = $envResp.ok -and ($envResp.status -ge 200 -and $envResp.status -lt 300)
  $codes['envelope']  = $envResp.status
  if ($envResp -and $envResp.headers -and $envResp.headers['X-ODIN-Trace-Id']) { $traceId = '' + $envResp.headers['X-ODIN-Trace-Id'] }
  Append-Block 'POST /v1/envelope (body first 500 chars)' (($envResp.text | Out-String).Substring(0, [Math]::Min(500, [Math]::Max(0, ($envResp.text | Out-String).Length))))
} else { $checks['envelope'] = $false; $codes['envelope'] = 0 }

# Translate
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $transBody = @{ payload = @{ intent = 'alpha@v1.hello'; args = @{ text = 'hi' }; from_sft = 'alpha@v1'; to_sft = 'beta@v1' } }
  $transResp = Invoke-JsonPost -url ($GATEWAY_URL.TrimEnd('/') + '/v1/translate') -obj $transBody -headers @{}
  $checks['translate'] = $transResp.ok -and ($transResp.status -ge 200 -and $transResp.status -lt 300)
  $codes['translate']  = $transResp.status
  Append-Block 'POST /v1/translate (body first 500 chars)' (($transResp.text | Out-String).Substring(0, [Math]::Min(500, [Math]::Max(0, ($transResp.text | Out-String).Length))))
} else { $checks['translate'] = $false; $codes['translate'] = 0 }

# Receipts list
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $hopsResp = Get-Text -url ($GATEWAY_URL.TrimEnd('/') + '/v1/receipts/hops') -headers @{}
  $checks['receipts_list'] = $hopsResp.ok -and ($hopsResp.status -ge 200 -and $hopsResp.status -lt 300)
  $codes['receipts_list']  = $hopsResp.status
  $sampleTxt = ($hopsResp.text | Out-String)
  Append-Block 'GET /v1/receipts/hops (first 500 chars)' ($sampleTxt.Substring(0, [Math]::Min(500, [Math]::Max(0, $sampleTxt.Length))))
  try { $arr = $sampleTxt | ConvertFrom-Json; if ($arr -and $arr.Count -gt 0) { $null = $arr[0] } } catch {}
} else { $checks['receipts_list'] = $false; $codes['receipts_list'] = 0 }

# Receipts chain by trace id
if ($traceId -and $traceId -ne '') {
  $chainResp = Get-Text -url ($GATEWAY_URL.TrimEnd('/') + '/v1/receipts/hops/chain/' + $traceId) -headers @{}
  $checks['receipts_chain'] = $chainResp.ok -and ($chainResp.status -ge 200 -and $chainResp.status -lt 300)
  $codes['receipts_chain']  = $chainResp.status
  $chainTxt = ($chainResp.text | Out-String)
  Append-Block 'GET /v1/receipts/hops/chain/{trace_id} (first 500 chars)' ($chainTxt.Substring(0, [Math]::Min(500, [Math]::Max(0, $chainTxt.Length))))
} else { $checks['receipts_chain'] = $false; $codes['receipts_chain'] = 0 }

# Relay hardened forward
if ($RELAY_URL -and $RELAY_URL -ne '') {
  $httpbinResp = Invoke-JsonPost -url ($RELAY_URL.TrimEnd('/') + '/relay') -obj @{ method = 'GET'; url = 'https://httpbin.org/json' } -headers @{}
  $checks['relay_httpbin'] = $httpbinResp.ok -and ($httpbinResp.status -ge 200 -and $httpbinResp.status -lt 300)
  $codes['relay_httpbin']  = $httpbinResp.status
  Append-Block 'POST /relay httpbin (first 500 chars)' (($httpbinResp.text | Out-String).Substring(0, [Math]::Min(500, [Math]::Max(0, ($httpbinResp.text | Out-String).Length))))

  $metaResp = Invoke-JsonPost -url ($RELAY_URL.TrimEnd('/') + '/relay') -obj @{ method = 'GET'; url = 'http://169.254.169.254/latest/meta-data/' } -headers @{}
  $codes['relay_ssrf_block'] = $metaResp.status
  $checks['relay_ssrf_block'] = -not ($metaResp.status -ge 200 -and $metaResp.status -lt 300)
  Append-Block 'POST /relay metadata (first 500 chars)' (($metaResp.text | Out-String).Substring(0, [Math]::Min(500, [Math]::Max(0, ($metaResp.text | Out-String).Length))))
} else { $checks['relay_httpbin'] = $false; $codes['relay_httpbin'] = 0; $checks['relay_ssrf_block'] = $false; $codes['relay_ssrf_block'] = 0 }

# Optional admin reload
if ($ADMIN_KEY -and $ADMIN_KEY -ne '' -and $GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $adminResp = Invoke-JsonPost -url ($GATEWAY_URL.TrimEnd('/') + '/v1/admin/reload') -obj @{} -headers @{ 'x-odin-admin-key' = $ADMIN_KEY }
  $checks['admin_reload'] = $adminResp.ok -and ($adminResp.status -ge 200 -and $adminResp.status -lt 300)
  $codes['admin_reload']  = $adminResp.status
  Append-Block 'POST /v1/admin/reload (first 500 chars)' (($adminResp.text | Out-String).Substring(0, [Math]::Min(500, [Math]::Max(0, ($adminResp.text | Out-String).Length))))
} else { $checks['admin_reload'] = $false; $codes['admin_reload'] = 0 }

# ===== Part D: Summary & README =====
$gatewayLine = $ci.GatewayImage + ':' + $TEST_TAG; if ($ci.GatewayTagDigest -ne '') { $gatewayLine += ' @ ' + $ci.GatewayTagDigest }
$relayLine   = $ci.RelayImage   + ':' + $TEST_TAG; if ($ci.RelayTagDigest   -ne '') { $relayLine   += ' @ ' + $ci.RelayTagDigest }
$releaseLine = $ci.GhRunUrl; if ($ci.GhRunStatus -ne '' -or $ci.GhRunConclusion -ne '') { $releaseLine += (' (' + $ci.GhRunStatus + '/' + $ci.GhRunConclusion + ')') }

function Row([string]$name, [string]$key) { return ('| ' + $name + ' | ' + (Mark($checks[$key])) + ' | ' + ([string]($codes[$key])) + ' |') }

$md = @()
$md += '# ODIN Protocol — System Status (auto-generated)'
$md += ''
$md += ('Generated: ' + $RunTs + ' UTC')
$md += ('Project: ' + $PROJECT_ID + '  |  Region: ' + $REGION)
$md += ''
$md += ('Gateway: ' + ($GATEWAY_URL -replace '\s+$',''))
$md += ('Relay  : ' + ($RELAY_URL -replace '\s+$',''))
$md += ''
$md += '## Summary'
$md += '| Check | Status | HTTP |'
$md += '|---|---|---|'
$md += (Row 'Gateway /metrics' 'gateway_metrics')
$md += (Row 'Relay /metrics' 'relay_metrics')
$md += (Row 'Envelope' 'envelope')
$md += (Row 'Translate' 'translate')
$md += (Row 'Receipts list' 'receipts_list')
$md += (Row 'Receipts chain' 'receipts_chain')
$md += (Row 'Relay httpbin' 'relay_httpbin')
$md += (Row 'Relay SSRF block' 'relay_ssrf_block')
$md += (Row 'Admin reload' 'admin_reload')
$md += ''
$md += '## Artifacts'
$md += ('- Gateway image: ' + $gatewayLine)
$md += ('- Relay image  : ' + $relayLine)
$md += ('- Release run  : ' + $releaseLine)
$md += ''
$md += '## Observability'
if (($checks['gateway_metrics']) -or ($checks['relay_metrics'])) {
  $md += '- /metrics responded.'
  if ($metricsNames.Count -gt 0) { $md += ('- Sample metrics: ' + (($metricsNames | Select-Object -First 5) -join ', ')) }
} else { $md += '- /metrics did not respond.' }
$md += '- Dashboard JSON available in `/marketplace/dashboards/`.'
$md += ''
$md += '## Security posture (runtime)'
$md += '- CI/CD via WIF (no static keys in repo).'
$md += ('- SSRF guard: ' + (Mark($checks['relay_ssrf_block'])))
$md += ('- Admin reload endpoint tested: ' + (Mark($checks['admin_reload'])))
$md += ''
$next = @()
foreach ($k in $checks.Keys) { if (-not $checks[$k]) { $next += ('- ' + $k + ': remediation needed (e.g., ensure service is deployed/configured)') } }
if ($next.Count -eq 0) { $md += '## Next actions'; $md += '- All checks passed.' }
else { $md += '## Next actions'; $md += ($next -join "`n") }
$md += ''
$md += ('Footer: Run at ' + $RunTs + ' UTC; PROJECT_ID=' + $PROJECT_ID + '; REGION=' + $REGION)
$md += ('Command: scripts/health-check.ps1 (PowerShell) with defaults; override via params/env vars')

$md -join "`n" | Out-File -FilePath $StatusMd -Encoding UTF8

Write-Host ''
Write-Host '=== ODIN Protocol — Health Check Summary ==='
Write-Host ('Gateway URL: ' + $GATEWAY_URL)
Write-Host ('Relay URL  : ' + $RELAY_URL)
Write-Host ('Gateway image @ tag: ' + $gatewayLine)
Write-Host ('Relay image   @ tag: ' + $relayLine)
Write-Host ('/metrics gateway: ' + (Mark($checks['gateway_metrics'])) + ' (' + [string]$codes['gateway_metrics'] + ')')
Write-Host ('/metrics relay  : ' + (Mark($checks['relay_metrics'])) + ' (' + [string]$codes['relay_metrics'] + ')')
Write-Host ('envelope       : ' + (Mark($checks['envelope'])) + ' (' + [string]$codes['envelope'] + ')')
Write-Host ('translate      : ' + (Mark($checks['translate'])) + ' (' + [string]$codes['translate'] + ')')
Write-Host ('receipts list  : ' + (Mark($checks['receipts_list'])) + ' (' + [string]$codes['receipts_list'] + ')')
Write-Host ('receipts chain : ' + (Mark($checks['receipts_chain'])) + ' (' + [string]$codes['receipts_chain'] + ')')
Write-Host ('relay httpbin  : ' + (Mark($checks['relay_httpbin'])) + ' (' + [string]$codes['relay_httpbin'] + ')')
Write-Host ('relay SSRF     : ' + (Mark($checks['relay_ssrf_block'])) + ' (' + [string]$codes['relay_ssrf_block'] + ')')
Write-Host ('admin reload   : ' + (Mark($checks['admin_reload'])) + ' (' + [string]$codes['admin_reload'] + ')')
Write-Host ''
Write-Host 'Saved:'
Write-Host ('- ' + $StatusMd)
Write-Host ('- ' + $Appendix)
