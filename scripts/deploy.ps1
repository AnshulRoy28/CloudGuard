# CloudGuard Deployment Script (Windows PowerShell)
# Deploys to Google Cloud Run with Cloud Scheduler

# Use Continue instead of Stop — gcloud writes info to stderr which PowerShell treats as errors
$ErrorActionPreference = "Continue"

# Colors
function Write-Header($msg) {
    Write-Host "`n============================================================" -ForegroundColor Blue
    Write-Host $msg -ForegroundColor Blue
    Write-Host "============================================================`n" -ForegroundColor Blue
}
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "  [X] $msg" -ForegroundColor Red; exit 1 }

# Load .env
$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) { Write-Err ".env not found. Run 'python scripts/setup.py' first." }

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
    }
}

$PROJECT_ID = $env:GCP_PROJECT_ID
$REGION = if ($env:CLOUD_RUN_REGION) { $env:CLOUD_RUN_REGION } else { "us-central1" }
$SERVICE_NAME = "cloudguard-api"
$SCHEDULER_JOB = "cloudguard-hourly-check"
$IMAGE_NAME = "gcr.io/$PROJECT_ID/$SERVICE_NAME"

Write-Header "CloudGuard Deployment"
Write-Host "  Project : $PROJECT_ID"
Write-Host "  Region  : $REGION"
Write-Host "  Service : $SERVICE_NAME"
Write-Host ""

# Pre-flight checks
Write-Header "Step 0: Pre-flight Checks"

$gcloudCheck = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $gcloudCheck) { Write-Err "gcloud CLI not found. Install from https://cloud.google.com/sdk" }
Write-OK "gcloud CLI found"

$dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCheck) { Write-Err "Docker not found. Install from https://docker.com" }
Write-OK "Docker found"

# Set project (redirect stderr to avoid false errors)
$null = gcloud config set project $PROJECT_ID 2>&1
Write-OK "Project set to $PROJECT_ID"

# Configure Docker for GCR
$null = gcloud auth configure-docker --quiet 2>&1
Write-OK "Docker configured for GCR"

# Step 1: Build
Write-Header "Step 1: Building Docker Image"
$projectRoot = Join-Path $PSScriptRoot ".."
docker build -t $IMAGE_NAME $projectRoot
if ($LASTEXITCODE -ne 0) { Write-Err "Docker build failed" }
Write-OK "Docker image built"

# Step 2: Push
Write-Header "Step 2: Pushing to Container Registry"
docker push $IMAGE_NAME
if ($LASTEXITCODE -ne 0) { Write-Err "Docker push failed" }
Write-OK "Image pushed to gcr.io"

# Step 3: Store secrets in Secret Manager
Write-Header "Step 3: Storing Secrets"

# Enable Secret Manager API
$null = gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID 2>&1
Write-OK "Secret Manager API enabled"

$secrets = @{
    "cloudguard-sendgrid-key" = $env:SENDGRID_API_KEY
    "cloudguard-jwt-secret"   = $env:JWT_SECRET
}

foreach ($name in $secrets.Keys) {
    $val = $secrets[$name]
    if (-not $val) { Write-Warn "Skipping secret $name (empty)"; continue }

    # Write value to temp file (piping to gcloud is unreliable on Windows)
    $tempFile = [System.IO.Path]::GetTempFileName()
    Set-Content -Path $tempFile -Value $val -NoNewline

    # Create or update secret
    $null = gcloud secrets describe $name --project=$PROJECT_ID 2>&1
    if ($LASTEXITCODE -ne 0) {
        $null = gcloud secrets create $name --data-file=$tempFile --project=$PROJECT_ID 2>&1
    } else {
        $null = gcloud secrets versions add $name --data-file=$tempFile --project=$PROJECT_ID 2>&1
    }

    Remove-Item $tempFile -Force
    Write-OK "Secret $name stored"
}

# Grant service account access to secrets
$SA_EMAIL = "cloudguard-agent@$PROJECT_ID.iam.gserviceaccount.com"
foreach ($name in $secrets.Keys) {
    $null = gcloud secrets add-iam-policy-binding $name `
        --member="serviceAccount:$SA_EMAIL" `
        --role="roles/secretmanager.secretAccessor" `
        --project=$PROJECT_ID 2>&1
}
Write-OK "Service account granted access to secrets"

# Step 4: Deploy to Cloud Run
Write-Header "Step 4: Deploying to Cloud Run"

# Write env vars to a YAML file (avoids comma issues with --set-env-vars)
$envYamlFile = Join-Path $env:TEMP "cloudguard-env.yaml"
@"
GCP_PROJECT_ID: "$PROJECT_ID"
BIGQUERY_BILLING_DATASET: "$($env:BIGQUERY_BILLING_DATASET)"
ALERT_EMAIL: "$($env:ALERT_EMAIL)"
MONTHLY_BUDGET_LIMIT: "$($env:MONTHLY_BUDGET_LIMIT)"
DRY_RUN_MODE: "$($env:DRY_RUN_MODE)"
ANOMALY_SENSITIVITY: "$($env:ANOMALY_SENSITIVITY)"
BLOCKLIST_TAGS: "$($env:BLOCKLIST_TAGS)"
CONFIRMATION_THRESHOLD_USD: "$($env:CONFIRMATION_THRESHOLD_USD)"
MAX_ACTIONS_PER_HOUR: "$($env:MAX_ACTIONS_PER_HOUR)"
"@ | Set-Content -Path $envYamlFile
Write-OK "Environment variables written to temp YAML"

gcloud run deploy $SERVICE_NAME `
    --image $IMAGE_NAME `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --memory 512Mi `
    --cpu 1 `
    --timeout 300 `
    --env-vars-file $envYamlFile `
    --set-secrets "SENDGRID_API_KEY=cloudguard-sendgrid-key:latest,JWT_SECRET=cloudguard-jwt-secret:latest" `
    --service-account $SA_EMAIL

Remove-Item $envYamlFile -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) { Write-Err "Cloud Run deployment failed" }
Write-OK "Deployed to Cloud Run"

# Get service URL
$SERVICE_URL = (gcloud run services describe $SERVICE_NAME --region $REGION --format "value(status.url)" 2>&1) | Select-Object -First 1
Write-OK "Service URL: $SERVICE_URL"

# Update .env with the deployed URL
$envContent = Get-Content $envFile -Raw
if ($envContent -match "API_BASE_URL=") {
    $envContent = $envContent -replace "API_BASE_URL=.*", "API_BASE_URL=$SERVICE_URL"
} else {
    $envContent += "`nAPI_BASE_URL=$SERVICE_URL"
}
Set-Content -Path $envFile -Value $envContent
Write-OK "Updated .env with API_BASE_URL"

# Step 5: Create Cloud Scheduler job
Write-Header "Step 5: Setting up Cloud Scheduler (hourly)"

# Enable Cloud Scheduler API
$null = gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID 2>&1

# Delete existing if present
$null = gcloud scheduler jobs delete $SCHEDULER_JOB --location $REGION --quiet 2>&1

gcloud scheduler jobs create http $SCHEDULER_JOB `
    --location $REGION `
    --schedule "0 * * * *" `
    --uri "$SERVICE_URL/api/v1/check" `
    --http-method GET `
    --oidc-service-account-email $SA_EMAIL

if ($LASTEXITCODE -ne 0) { Write-Warn "Scheduler setup failed - you may need to create an App Engine app first" }
else { Write-OK "Cloud Scheduler job created (runs every hour)" }

# Step 6: Health check
Write-Header "Step 6: Testing Deployment"

Start-Sleep -Seconds 5  # Wait for service to start

try {
    $response = Invoke-WebRequest -Uri "$SERVICE_URL/health" -UseBasicParsing -TimeoutSec 10
    $health = $response.Content | ConvertFrom-Json
    if ($health.status -eq "healthy") {
        Write-OK "Health check passed"
    } else {
        Write-Warn "Health check returned: $($health.status)"
    }
} catch {
    Write-Warn "Health check failed (service may still be starting)"
}

# Done
Write-Header "Deployment Complete!"
Write-Host @"

  CloudGuard is now running 24/7!

  Service URL : $SERVICE_URL
  Health Check: $SERVICE_URL/health
  Trigger Check: $SERVICE_URL/api/v1/check
  Test Email : $SERVICE_URL/api/v1/test-email
  Scheduler  : Runs every hour at :00

  View logs:
    gcloud run logs read --service=$SERVICE_NAME --region=$REGION

  Trigger manual check:
    Invoke-WebRequest "$SERVICE_URL/api/v1/check" -UseBasicParsing

"@ -ForegroundColor Cyan
