#!/bin/bash
# CloudGuard Deployment Script
# Deploys to Google Cloud Run with Cloud Scheduler

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

# Check if .env exists
if [ ! -f .env ]; then
    print_error ".env file not found. Run 'python scripts/setup.py' first."
fi

# Load environment variables
source .env

# Configuration
PROJECT_ID="${GCP_PROJECT_ID}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="cloudguard-api"
SCHEDULER_JOB="cloudguard-hourly-check"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

print_header "CloudGuard Deployment"

echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Step 1: Build Docker image
print_header "Step 1: Building Docker Image"
docker build -t ${IMAGE_NAME} .
print_success "Docker image built"

# Step 2: Push to Container Registry
print_header "Step 2: Pushing to Container Registry"
docker push ${IMAGE_NAME}
print_success "Image pushed to gcr.io"

# Step 3: Deploy to Cloud Run
print_header "Step 3: Deploying to Cloud Run"

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --set-env-vars "GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
    --set-env-vars "BIGQUERY_BILLING_DATASET=${BIGQUERY_BILLING_DATASET}" \
    --set-env-vars "ALERT_EMAIL=${ALERT_EMAIL}" \
    --set-env-vars "MONTHLY_BUDGET_LIMIT=${MONTHLY_BUDGET_LIMIT}" \
    --set-env-vars "DRY_RUN_MODE=${DRY_RUN_MODE}" \
    --set-env-vars "ANOMALY_SENSITIVITY=${ANOMALY_SENSITIVITY}" \
    --set-secrets "SENDGRID_API_KEY=sendgrid-api-key:latest" \
    --set-secrets "JWT_SECRET=jwt-secret:latest" \
    --set-secrets "GCP_SERVICE_ACCOUNT_JSON=gcp-sa-key:latest"

print_success "Deployed to Cloud Run"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

echo ""
print_success "Service URL: ${SERVICE_URL}"

# Step 4: Create Cloud Scheduler job
print_header "Step 4: Setting up Cloud Scheduler"

# Delete existing job if exists
gcloud scheduler jobs delete ${SCHEDULER_JOB} \
    --location ${REGION} \
    --quiet 2>/dev/null || true

# Create new scheduler job (runs every hour)
gcloud scheduler jobs create http ${SCHEDULER_JOB} \
    --location ${REGION} \
    --schedule "0 * * * *" \
    --uri "${SERVICE_URL}/api/v1/check" \
    --http-method GET \
    --oidc-service-account-email "cloudguard-agent@${PROJECT_ID}.iam.gserviceaccount.com"

print_success "Cloud Scheduler job created (runs every hour)"

# Step 5: Test deployment
print_header "Step 5: Testing Deployment"

HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health")

if [ "$HEALTH_CHECK" == "200" ]; then
    print_success "Health check passed"
else
    print_warning "Health check returned ${HEALTH_CHECK}"
fi

print_header "Deployment Complete!"

echo -e "
${GREEN}CloudGuard is now running!${NC}

${BLUE}Service URL:${NC} ${SERVICE_URL}
${BLUE}Health Check:${NC} ${SERVICE_URL}/health
${BLUE}Scheduler:${NC} Runs every hour at :00

${YELLOW}Next Steps:${NC}
1. Update your .env with: API_BASE_URL=${SERVICE_URL}
2. Test the health endpoint manually
3. Wait for the first scheduled run (or manually trigger)

${YELLOW}To view logs:${NC}
gcloud run logs read --service=${SERVICE_NAME} --region=${REGION}

${YELLOW}To trigger a manual check:${NC}
curl ${SERVICE_URL}/api/v1/check
"
