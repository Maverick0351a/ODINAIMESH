# ODIN Health Check (PowerShell 5.1)
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

function Get-Default($val, $fallback) { if ($null -ne $val -and $val -ne '') { $val } else { $fallback } }

$PROJECT_ID      = Get-Default $PROJECT_ID     (Get-Default $env:PROJECT_ID     'odin-producer')
$REGION          = Get-Default $REGION         (Get-Default $env:REGION         'us-central1')
$GATEWAY_SERVICE = Get-Default $GATEWAY_SERVICE(Get-Default $env:GATEWAY_SERVICE 'odin-gateway')
$RELAY_SERVICE   = Get-Default $RELAY_SERVICE  (Get-Default $env:RELAY_SERVICE   'odin-relay')
$AR_REPO         = Get-Default $AR_REPO        (Get-Default $env:AR_REPO        'odin')
$TEST_TAG        = Get-Default $TEST_TAG       (Get-Default $env:TEST_TAG       'v0.0.1')
$ADMIN_KEY       = Get-Default $ADMIN_KEY      (Get-Default $env:ADMIN_KEY      '')
$USE_ID_TOKEN    = Get-Default $env:ODIN_USE_ID_TOKEN '1'

$RunTs = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
$Root = (Get-Location).Path
$DocsDir = Join-Path $Root 'docs'
New-Item -ItemType Directory -Path $DocsDir -Force | Out-Null
$Appendix = Join-Path $DocsDir 'STATUS_README.appendix.txt'
$StatusMd = Join-Path $DocsDir 'STATUS_README.md'
'' | Out-File -FilePath $Appendix -Encoding UTF8  # truncate appendix for idempotent runs

function Append-Block([string]$Title, [string]$Content) {
  $line = ('# ' + $Title)
  ($line + "`n" + $Content + "`n`n") | Out-File -FilePath $Appendix -Encoding UTF8 -Append
}

function Mark([bool]$ok) { if ($ok) { '✅' } else { '❌' } }

function Get-IdToken([string]$aud) {
  if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) { return '' }
  $args = @('auth','print-identity-token','--audiences', $aud)
  $tok = & gcloud @args 2>&1
  if ($LASTEXITCODE -ne 0) { return '' }
  return ($tok | Out-String).Trim()
}

function Get-AuthHeaders([string]$baseUrl) {
  $h = @{}
  if ($USE_ID_TOKEN -and $USE_ID_TOKEN -ne '0' -and $baseUrl -and $baseUrl -ne '') {
    $t = Get-IdToken $baseUrl
    if ($t -and $t -ne '') { $h['Authorization'] = ('Bearer ' + $t) }
  }
  return $h
}

function Get-Text([string]$url, [hashtable]$headers) {
  if (-not $headers) { $headers = @{} }
  try {
    $resp = Invoke-WebRequest -Uri $url -Method GET -Headers $headers -UseBasicParsing -TimeoutSec 30
    return [PSCustomObject]@{ ok=$true; status=[int]$resp.StatusCode; text=$resp.Content; headers=$resp.Headers }
  } catch {
    $msg = $_ | Out-String; $status = 0
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $status = [int]$_.Exception.Response.StatusCode }
    return [PSCustomObject]@{ ok=$false; status=$status; text=$msg; headers=@{} }
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
    return [PSCustomObject]@{ ok=$true; status=[int]$resp.StatusCode; text=$bodyText; headers=$resp.Headers; json=$parsed }
  } catch {
    $status = 0; $body = ''
    if ($_.Exception.Response) {
      try { $status = [int]$_.Exception.Response.StatusCode } catch {}
      try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $body = $sr.ReadToEnd() } catch { $body = ($_.Exception.Message) }
    } else { $body = ($_.Exception.Message) }
    $parsed = $null; try { $parsed = $body | ConvertFrom-Json } catch { $parsed = $null }
    return [PSCustomObject]@{ ok=$false; status=$status; text=$body; headers=@{}; json=$parsed }
  }
}

function Get-RunUrl([string]$service, [string]$region) {
  $args = @('run','services','describe',$service,'--region',$region,'--format=value(status.url)')
  $out = & gcloud @args 2>&1
  if ($LASTEXITCODE -ne 0) { return '' }
  return ($out | Out-String).Trim()
}

# Part B — CI/artifacts
$ci = [PSCustomObject]@{
  Project=$PROJECT_ID; Region=$REGION; TestTag=$TEST_TAG;
  GatewayImage = "us-central1-docker.pkg.dev/$PROJECT_ID/$AR_REPO/gateway";
  RelayImage   = "us-central1-docker.pkg.dev/$PROJECT_ID/$AR_REPO/relay";
  GatewayTagDigest=''; RelayTagDigest=''; GhRunUrl=''; GhRunStatus=''; GhRunConclusion=''
}

$gcloudOk = $true
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) { $gcloudOk = $false; Append-Block 'ERROR' 'gcloud CLI not found in PATH.' }

if ($gcloudOk) {
  $setOut = & gcloud @('config','set','project',$PROJECT_ID) 2>&1
  Append-Block 'gcloud config set project' ($setOut | Out-String)

  $gwTagsRaw = & gcloud @('artifacts','docker','tags','list',$ci.GatewayImage,'--format','json') 2>&1
  $rlTagsRaw = & gcloud @('artifacts','docker','tags','list',$ci.RelayImage,'--format','json') 2>&1
  Append-Block 'AR: gateway tags (raw)' ($gwTagsRaw | Out-String)
  Append-Block 'AR: relay tags (raw)' ($rlTagsRaw | Out-String)
  $gwTags = $null; $rlTags = $null
  try { $gwTags = $gwTagsRaw | ConvertFrom-Json } catch {}
  try { $rlTags = $rlTagsRaw | ConvertFrom-Json } catch {}
  if ($gwTags) { $m = $gwTags | Where-Object { $_.tag -eq $TEST_TAG } | Select-Object -First 1; if ($m) { $ci.GatewayTagDigest = $m.digest } }
  if ($rlTags) { $m = $rlTags | Where-Object { $_.tag -eq $TEST_TAG } | Select-Object -First 1; if ($m) { $ci.RelayTagDigest = $m.digest } }
}

# Optional GH Actions details (if gh available)
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
      $sample = (($keyLines | Select-Object -First 30) -join "`n")
      Append-Block 'gh run view (filtered logs)' $sample
    }
  } catch { Append-Block 'gh error' ($_ | Out-String) }
}

# Part C — Discover URLs
$GATEWAY_URL = ''; $RELAY_URL = ''
if ($gcloudOk) {
  $GATEWAY_URL = Get-RunUrl -service $GATEWAY_SERVICE -region $REGION
  $RELAY_URL   = Get-RunUrl -service $RELAY_SERVICE -region $REGION
}
Append-Block 'Cloud Run URL (gateway)' $GATEWAY_URL
Append-Block 'Cloud Run URL (relay)' $RELAY_URL

$checks = @{}
$codes  = @{}

# Metrics
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $gw = Get-Text -url ($GATEWAY_URL.TrimEnd('/') + '/metrics') -headers (Get-AuthHeaders $GATEWAY_URL)
  $checks['gateway_metrics'] = $gw.ok -and ($gw.status -ge 200 -and $gw.status -lt 400)
  $codes['gateway_metrics'] = $gw.status
  Append-Block 'Gateway /metrics (first 10 lines)' (((($gw.text | Out-String) -split "`n") | Select-Object -First 10) -join "`n")
} else { $checks['gateway_metrics'] = $false; $codes['gateway_metrics'] = 0 }

if ($RELAY_URL -and $RELAY_URL -ne '') {
  $rl = Get-Text -url ($RELAY_URL.TrimEnd('/') + '/metrics') -headers (Get-AuthHeaders $RELAY_URL)
  $checks['relay_metrics'] = $rl.ok -and ($rl.status -ge 200 -and $rl.status -lt 400)
  $codes['relay_metrics'] = $rl.status
  Append-Block 'Relay /metrics (first 10 lines)' (((($rl.text | Out-String) -split "`n") | Select-Object -First 10) -join "`n")
} else { $checks['relay_metrics'] = $false; $codes['relay_metrics'] = 0 }

# Envelope
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $envResp = Invoke-JsonPost -url ($GATEWAY_URL.TrimEnd('/') + '/v1/envelope') -obj @{ payload = @{ hello = 'world' } } -headers (Get-AuthHeaders $GATEWAY_URL)
  $checks['envelope'] = $envResp.ok -and ($envResp.status -ge 200 -and $envResp.status -lt 300)
  $codes['envelope']  = $envResp.status
  Append-Block 'POST /v1/envelope (first 500 chars)' ((($envResp.text | Out-String)).Substring(0, [Math]::Min(500, [Math]::Max(0, (($envResp.text | Out-String)).Length))))
} else { $checks['envelope'] = $false; $codes['envelope'] = 0 }

# Translate
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $transBody = @{ payload = @{ intent = 'alpha@v1.hello'; args = @{ text = 'hi' }; from_sft = 'alpha@v1'; to_sft = 'beta@v1' } }
  $transResp = Invoke-JsonPost -url ($GATEWAY_URL.TrimEnd('/') + '/v1/translate') -obj $transBody -headers (Get-AuthHeaders $GATEWAY_URL)
  $checks['translate'] = $transResp.ok -and ($transResp.status -ge 200 -and $transResp.status -lt 300)
  $codes['translate']  = $transResp.status
  Append-Block 'POST /v1/translate (first 500 chars)' ((($transResp.text | Out-String)).Substring(0, [Math]::Min(500, [Math]::Max(0, (($transResp.text | Out-String)).Length))))
} else { $checks['translate'] = $false; $codes['translate'] = 0 }

# Receipts
if ($GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $hopsResp = Get-Text -url ($GATEWAY_URL.TrimEnd('/') + '/v1/receipts/hops') -headers (Get-AuthHeaders $GATEWAY_URL)
  $checks['receipts_list'] = $hopsResp.ok -and ($hopsResp.status -ge 200 -and $hopsResp.status -lt 300)
  $codes['receipts_list']  = $hopsResp.status
  $sampleTxt = ($hopsResp.text | Out-String)
  Append-Block 'GET /v1/receipts/hops (first 500 chars)' ($sampleTxt.Substring(0, [Math]::Min(500, [Math]::Max(0, $sampleTxt.Length))))
} else { $checks['receipts_list'] = $false; $codes['receipts_list'] = 0 }

# Relay hardened forward
if ($RELAY_URL -and $RELAY_URL -ne '') {
  $httpbinResp = Invoke-JsonPost -url ($RELAY_URL.TrimEnd('/') + '/relay') -obj @{ method = 'GET'; url = 'https://httpbin.org/json' } -headers (Get-AuthHeaders $RELAY_URL)
  $checks['relay_httpbin'] = $httpbinResp.ok -and ($httpbinResp.status -ge 200 -and $httpbinResp.status -lt 300)
  $codes['relay_httpbin']  = $httpbinResp.status
  Append-Block 'POST /relay httpbin (first 500 chars)' ((($httpbinResp.text | Out-String)).Substring(0, [Math]::Min(500, [Math]::Max(0, (($httpbinResp.text | Out-String)).Length))))

  $metaResp = Invoke-JsonPost -url ($RELAY_URL.TrimEnd('/') + '/relay') -obj @{ method = 'GET'; url = 'http://169.254.169.254/latest/meta-data/' } -headers (Get-AuthHeaders $RELAY_URL)
  $codes['relay_ssrf_block'] = $metaResp.status
  $checks['relay_ssrf_block'] = -not ($metaResp.status -ge 200 -and $metaResp.status -lt 300)
  Append-Block 'POST /relay metadata (first 500 chars)' ((($metaResp.text | Out-String)).Substring(0, [Math]::Min(500, [Math]::Max(0, (($metaResp.text | Out-String)).Length))))
} else { $checks['relay_httpbin'] = $false; $codes['relay_httpbin'] = 0; $checks['relay_ssrf_block'] = $false; $codes['relay_ssrf_block'] = 0 }

# Optional admin reload
if ($ADMIN_KEY -and $ADMIN_KEY -ne '' -and $GATEWAY_URL -and $GATEWAY_URL -ne '') {
  $adminResp = Invoke-JsonPost -url ($GATEWAY_URL.TrimEnd('/') + '/v1/admin/reload') -obj @{} -headers @{ 'x-odin-admin-key' = $ADMIN_KEY }
  $checks['admin_reload'] = $adminResp.ok -and ($adminResp.status -ge 200 -and $adminResp.status -lt 300)
  $codes['admin_reload']  = $adminResp.status
  Append-Block 'POST /v1/admin/reload (first 500 chars)' ((($adminResp.text | Out-String)).Substring(0, [Math]::Min(500, [Math]::Max(0, (($adminResp.text | Out-String)).Length))))
} else { $checks['admin_reload'] = $false; $codes['admin_reload'] = 0 }

# Summary & README
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
$md += (Row 'Relay httpbin' 'relay_httpbin')
$md += (Row 'Relay SSRF block' 'relay_ssrf_block')
$md += (Row 'Admin reload' 'admin_reload')
$md += ''
$md += '## Artifacts'
$md += ('- Gateway image: ' + $gatewayLine)
$md += ('- Relay image  : ' + $relayLine)
$md += ('- Release run  : ' + $releaseLine)
$md += ''
$md += '## Notes'
$md += '- Cloud Run services may require auth; 403 indicates auth needed rather than outage.'
$md += ''
$md += ('Footer: Run at ' + $RunTs + ' UTC; PROJECT_ID=' + $PROJECT_ID + '; REGION=' + $REGION)

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
Write-Host ('relay httpbin  : ' + (Mark($checks['relay_httpbin'])) + ' (' + [string]$codes['relay_httpbin'] + ')')
Write-Host ('relay SSRF     : ' + (Mark($checks['relay_ssrf_block'])) + ' (' + [string]$codes['relay_ssrf_block'] + ')')
Write-Host ('admin reload   : ' + (Mark($checks['admin_reload'])) + ' (' + [string]$codes['admin_reload'] + ')')
Write-Host ''
Write-Host 'Saved:'
Write-Host ('- ' + $StatusMd)
Write-Host ('- ' + $Appendix)
