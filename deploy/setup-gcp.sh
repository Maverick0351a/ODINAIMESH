#!/bin/bash

# ODIN Google Cloud Platform Setup Script
# Usage: ./setup-gcp.sh <project-id> <region>

set -e

PROJECT_ID=${1:-"odin-dev"}
REGION=${2:-"us-central1"}
REPO_NAME="odin"

echo "🚀 Setting up ODIN on Google Cloud Platform"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Repository: $REPO_NAME"

# Set the project
gcloud config set project $PROJECT_ID

echo "📋 Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    cloudkms.googleapis.com \
    iam.googleapis.com \
    monitoring.googleapis.com \
    storage-api.googleapis.com \
    cloudbuild.googleapis.com

echo "🏗️ Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="ODIN container images" || echo "Repository already exists"

echo "🔐 Creating KMS key ring and signing key..."
gcloud kms keyrings create odin-keys \
    --location=$REGION || echo "Key ring already exists"

gcloud kms keys create gw-ed25519 \
    --location=$REGION \
    --keyring=odin-keys \
    --purpose=asymmetric-signing \
    --default-algorithm=ec-sign-ed25519 || echo "Key already exists"

echo "🗄️ Initializing Firestore..."
gcloud firestore databases create \
    --region=$REGION \
    --type=firestore-native || echo "Firestore already initialized"

echo "📦 Creating Cloud Storage bucket for Realm Packs..."
gsutil mb -p $PROJECT_ID -l $REGION gs://$PROJECT_ID-realm-packs || echo "Bucket already exists"
gsutil versioning set on gs://$PROJECT_ID-realm-packs

echo "🔑 Creating service accounts..."

# Deployer service account (for GitHub Actions)
gcloud iam service-accounts create odin-deployer \
    --display-name="ODIN Deployer" \
    --description="Service account for GitHub Actions deployments" || echo "SA already exists"

# Gateway service account
gcloud iam service-accounts create odin-gateway \
    --display-name="ODIN Gateway" \
    --description="Service account for Gateway service" || echo "SA already exists"

# Relay service account
gcloud iam service-accounts create odin-relay \
    --display-name="ODIN Relay" \
    --description="Service account for Relay service" || echo "SA already exists"

# Site service account
gcloud iam service-accounts create odin-site \
    --display-name="ODIN Site" \
    --description="Service account for Site service" || echo "SA already exists"

echo "🎭 Assigning IAM roles..."

# Deployer permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Gateway permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudkms.signerVerifier"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-gateway@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.metricWriter"

# Relay permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-relay@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.metricWriter"

# Site permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:odin-site@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.metricWriter"

echo "🔐 Creating secrets..."

# Create admin key secret
echo "Enter admin key for ODIN (or press Enter for auto-generated):"
read -s ADMIN_KEY
if [ -z "$ADMIN_KEY" ]; then
    ADMIN_KEY=$(openssl rand -base64 32)
    echo "Generated admin key: $ADMIN_KEY"
fi

echo -n "$ADMIN_KEY" | gcloud secrets create ODIN_ADMIN_KEY \
    --replication-policy="automatic" \
    --data-file=- || echo "Secret already exists"

echo "🌐 Setting up Workload Identity Federation..."

# Create workload identity pool
gcloud iam workload-identity-pools create "odin-github-pool" \
    --location="global" \
    --display-name="ODIN GitHub Pool" || echo "Pool already exists"

# Create workload identity provider
gcloud iam workload-identity-pools providers create-oidc "odin-github-provider" \
    --location="global" \
    --workload-identity-pool="odin-github-pool" \
    --display-name="ODIN GitHub Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com" || echo "Provider already exists"

# Get the provider name for GitHub secrets
WIF_PROVIDER="projects/$(gcloud config get-value project --quiet)/locations/global/workloadIdentityPools/odin-github-pool/providers/odin-github-provider"

echo "📋 Setup complete! Add these secrets to your GitHub repository:"
echo ""
echo "GCP_PROJECT_ID_DEV: $PROJECT_ID"
echo "GCP_WIF_PROVIDER: $WIF_PROVIDER"
echo ""
echo "To complete the setup:"
echo "1. Add the above secrets to your GitHub repository settings"
echo "2. Configure the service account impersonation:"
echo ""
echo "   gcloud iam service-accounts add-iam-policy-binding \\"
echo "     odin-deployer@$PROJECT_ID.iam.gserviceaccount.com \\"
echo "     --role=roles/iam.workloadIdentityUser \\"
echo "     --member=\"principalSet://iam.googleapis.com/$WIF_PROVIDER/attribute.repository/YOUR_GITHUB_USERNAME/ODINAIMESH\""
echo ""
echo "3. Push to main branch to trigger deployment"
echo ""
echo "🎉 ODIN GCP setup complete!"
