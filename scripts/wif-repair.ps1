$ErrorActionPreference = 'Stop'

# Known values
$PROJECT_ID = 'valued-lambda-469623-b4'
$PROJECT_NUMBER = '35374236962'
$SA_EMAIL = 'gh-actions-deployer@valued-lambda-469623-b4.iam.gserviceaccount.com'
$POOL_ID = 'github-pool'
$PROVIDER_ID = 'github-oidc'
$REPO_SLUG = 'Maverick0351a/ODINAIMESH'
$ISSUER = 'https://token.actions.githubusercontent.com'
# Condition (tags only) using assertion.* and method-style startsWith
$CONDITION_EXPR = "assertion.ref.startsWith('refs/tags/')"
$CONDITION = "expression=$CONDITION_EXPR,title=github-tags,description=GitHub tags only"
$POOL_RESOURCE = "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID"
$PROVIDER_RESOURCE = "$POOL_RESOURCE/providers/$PROVIDER_ID"

Write-Host "STEP 1) Ensure correct project and account"
Write-Host "CMD> gcloud config set project $PROJECT_ID"
(gcloud config set project $PROJECT_ID --quiet) | Out-Host
Write-Host "CMD> gcloud auth list"
(gcloud auth list --format='table(account,status)') | Out-Host
Write-Host "CMD> gcloud config list account"
(gcloud config list account --format='value(core.account)') | Out-Host

Write-Host "`nSTEP 2) Verify/create Workload Identity Pool and Provider"
Write-Host "CMD> gcloud iam workload-identity-pools describe $POOL_ID --location=global"
$poolName = (gcloud iam workload-identity-pools describe $POOL_ID --location=global --format="value(name)" 2>$null)
if (-not $poolName) {
  Write-Host "CMD> gcloud iam workload-identity-pools create $POOL_ID --location=global --display-name 'GitHub Actions Pool'"
  (gcloud iam workload-identity-pools create $POOL_ID --location=global --display-name='GitHub Actions Pool' --format='value(name)') | Out-Host
} else { Write-Host "Pool exists: $poolName" }

Write-Host "CMD> gcloud iam workload-identity-pools providers describe $PROVIDER_ID --location=global --workload-identity-pool=$POOL_ID"
$provName = (gcloud iam workload-identity-pools providers describe $PROVIDER_ID --location=global --workload-identity-pool=$POOL_ID --format='value(name)' 2>$null)
if (-not $provName) {
  Write-Host "CMD> gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID --location=global --workload-identity-pool=$POOL_ID --display-name 'GitHub OIDC Provider' --issuer-uri=$ISSUER --attribute-mapping 'google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.repository_owner=assertion.repository_owner' --attribute-condition 'attribute.repository == ''$REPO_SLUG'''"
  (gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID `
    --location=global `
    --workload-identity-pool=$POOL_ID `
    --display-name='GitHub OIDC Provider' `
    --issuer-uri=$ISSUER `
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.repository_owner=assertion.repository_owner" `
    --attribute-condition="attribute.repository == '$REPO_SLUG'" `
    --format='value(name)') | Out-Host
} else { Write-Host "Provider exists: $provName" }

$GCP_WIF_PROVIDER = $PROVIDER_RESOURCE
Write-Host "GCP_WIF_PROVIDER=$GCP_WIF_PROVIDER"

Write-Host "`nSTEP 3) Apply Workload Identity User binding (tags only)"
$MEMBER = "principalSet://iam.googleapis.com/$POOL_RESOURCE/attribute.repository/$REPO_SLUG"
Write-Host "Member: $MEMBER"
Write-Host "Condition: $CONDITION"
Write-Host "CMD> Remove any existing unconditional binding (ignore error if absent)"
try {
  (gcloud iam service-accounts remove-iam-policy-binding $SA_EMAIL --role=roles/iam.workloadIdentityUser --member="$MEMBER" --format=json) | Out-Host
} catch { Write-Host "No unconditional binding to remove or removal not needed." }

# Use a temp JSON file for the condition to avoid CLI parsing issues with commas in expression
$condFile = [System.IO.Path]::Combine($env:TEMP, "wif-condition.json")
@{
  expression = $CONDITION_EXPR
  title = 'github-tags'
  description = 'GitHub tags only'
} | ConvertTo-Json | Set-Content -Path $condFile -Encoding ASCII

Write-Host "CMD> gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL --role=roles/iam.workloadIdentityUser --member='$MEMBER' --condition-from-file='$condFile'"
(gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL --role=roles/iam.workloadIdentityUser --member="$MEMBER" --condition-from-file="$condFile" --format=json) | Out-Host

Write-Host "`nSTEP 4) Re-grant deployer roles (idempotent)"
Write-Host "CMD> roles/run.admin, roles/artifactregistry.writer, roles/iam.serviceAccountTokenCreator"
(gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$SA_EMAIL" --role roles/run.admin --format=json) | Out-Host
(gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$SA_EMAIL" --role roles/artifactregistry.writer --format=json) | Out-Host
(gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$SA_EMAIL" --role roles/iam.serviceAccountTokenCreator --format=json) | Out-Host

Write-Host "`nSTEP 5) Sanity checks"
Write-Host "CMD> provider describe (name, issuerUri, attributeCondition)"
(gcloud iam workload-identity-pools providers describe $PROVIDER_ID --location=global --workload-identity-pool=$POOL_ID --format="value(name,oidc.issuerUri,attributeCondition)") | Out-Host
Write-Host "CMD> service account IAM policy (YAML)"
(gcloud iam service-accounts get-iam-policy $SA_EMAIL --format=yaml) | Out-Host

Write-Host "`nSTEP 6) Fixed if/else block for gh CLI"
$repoSlug = 'Maverick0351a/ODINAIMESH'
if (Get-Command gh -ErrorAction SilentlyContinue) {
  gh --version | Out-Host
  $url = "https://github.com/$repoSlug/actions/workflows/release.yml?query=tag%3Av0.0.1"
  try {
    $runs = gh run list --workflow release.yml --json databaseId,headTag,status,url --limit 20 | ConvertFrom-Json
    $match = $runs | Where-Object { $_.headTag -eq 'v0.0.1' } | Select-Object -First 1
    if ($match -and $match.url) { Write-Host "Release run: $($match.url)" } else { Write-Host "No run found for tag v0.0.1. See: $url" }
  } catch {
    Write-Host "Failed to query gh runs. See: $url"
  }
} else {
  Write-Host "gh CLI not found. Visit: https://github.com/$repoSlug/actions/workflows/release.yml?query=tag%3Av0.0.1"
}

Write-Host "`nFinal outputs:"
Write-Host "GCP_WIF_PROVIDER = $GCP_WIF_PROVIDER"
Write-Host "GCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT = $SA_EMAIL"
