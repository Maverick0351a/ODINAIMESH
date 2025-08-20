param(
  [string]$Project = "odin-468307",
  [string]$Region = "us-central1",
  [string]$ServiceGateway = "odin-gateway",
  [Parameter(Mandatory=$true)][string]$NotificationChannelId,
  [string]$BaseUrl = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($NotificationChannelId)) {
  Write-Error "NotificationChannelId is required. Run: gcloud alpha monitoring channels list --project $Project"
  exit 1
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
  $BaseUrl = "https://$ServiceGateway-$Project.$Region.run.app"
}

Write-Host "Using BaseUrl: $BaseUrl" -ForegroundColor Cyan

function New-TempJsonFile {
  param([string]$Content)
  $f = New-TemporaryFile
  $Content | Out-File -FilePath $f -Encoding utf8
  return $f
}

# 1) Uptime check on /health (idempotent: create if missing)
try {
  & gcloud monitoring uptime describe odin-gateway-health --project $Project 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Uptime check 'odin-gateway-health' already exists — skipping create." -ForegroundColor Yellow
  } else {
    throw "not-exists"
  }
} catch {
  Write-Host "Creating uptime check 'odin-gateway-health'..." -ForegroundColor Green
  & gcloud monitoring uptime create odin-gateway-health `
    --project $Project `
    --path "/health" `
    --http-method "GET" `
    --period "60s" `
    --timeout "10s" `
    --checked-resource "uptime-url" `
    --url $BaseUrl
}

# 2) Error-rate alert (5xx > 2% for 5m)
$errPolicy = @"
{
  "displayName": "ODIN Gateway - Error rate >2% (5m)",
  "combiner": "OR",
  "conditions": [{
    "displayName": "5xx ratio > 0.02",
    "conditionRatio": {
      "ratioThreshold": {
        "filter": "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" metric.label.\"response_code_class\"=\"5xx\" resource.label.\"service_name\"=\"$ServiceGateway\"",
        "denominatorFilter": "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"$ServiceGateway\"",
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0.02,
        "duration": "300s"
      },
      "evaluationMissingData": "EVALUATION_MISSING_DATA_NO_OP"
    }
  }],
  "notificationChannels": ["projects/$Project/notificationChannels/$NotificationChannelId"]
}
"@
$errFile = New-TempJsonFile -Content $errPolicy
Write-Host "Creating error-rate alert policy..." -ForegroundColor Green
& gcloud alpha monitoring policies create --project $Project --policy-from-file=$errFile

# 3) Latency alert (p95 > 1.5s for 5m)
$latPolicy = @"
{
  "displayName": "ODIN Gateway - p95 latency >1.5s (5m)",
  "combiner": "OR",
  "conditions": [{
    "displayName": "p95 request latency",
    "conditionThreshold": {
      "filter": "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"$ServiceGateway\"",
      "aggregations": [{
        "alignmentPeriod": "60s",
        "perSeriesAligner": "ALIGN_PERCENTILE_95"
      }],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 1.5,
      "duration": "300s"
    }
  }],
  "notificationChannels": ["projects/$Project/notificationChannels/$NotificationChannelId"]
}
"@
$latFile = New-TempJsonFile -Content $latPolicy
Write-Host "Creating latency alert policy..." -ForegroundColor Green
& gcloud alpha monitoring policies create --project $Project --policy-from-file=$latFile

# 4) Logs-based metric for policy blocks, + alert if bursts (idempotent metric)
& gcloud logging metrics describe odin_policy_block_count --project $Project 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Creating logs-based metric 'odin_policy_block_count'..." -ForegroundColor Green
  & gcloud logging metrics create odin_policy_block_count `
    --project $Project `
    --description "Count of HEL/policy blocks" `
    --log-filter "resource.type=\"cloud_run_revision\" AND (jsonPayload.error=\"odin.policy.blocked\" OR textPayload: \"odin.policy.blocked\")"
} else {
  Write-Host "Logs-based metric 'odin_policy_block_count' already exists — skipping create." -ForegroundColor Yellow
}

$polPolicy = @"
{
  "displayName": "ODIN Gateway - Policy blocks burst (>=5 in 5m)",
  "combiner": "OR",
  "conditions": [{
    "displayName": "policy blocks >= 5 in 5m",
    "conditionThreshold": {
      "filter": "metric.type=\"logging.googleapis.com/user/odin_policy_block_count\" resource.type=\"cloud_run_revision\"",
      "aggregations": [{
        "alignmentPeriod": "300s",
        "perSeriesAligner": "ALIGN_DELTA",
        "crossSeriesReducer": "REDUCE_SUM",
        "groupByFields": ["resource.label.\"service_name\""]
      }],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 5,
      "duration": "0s"
    }
  }],
  "notificationChannels": ["projects/$Project/notificationChannels/$NotificationChannelId"]
}
"@
$polFile = New-TempJsonFile -Content $polPolicy
Write-Host "Creating policy-blocks burst alert policy..." -ForegroundColor Green
& gcloud alpha monitoring policies create --project $Project --policy-from-file=$polFile

Write-Host "Done." -ForegroundColor Cyan
