#!/bin/bash

# ODIN Cloud Run Startup Script
# Initializes Firestore collections and indexes

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
echo "Initializing ODIN on project: $PROJECT_ID"

# Function to create Firestore indexes
create_indexes() {
    echo "Creating Firestore indexes..."
    
    # Create composite index for runs (project_id, created_at desc)
    gcloud firestore indexes composite create \
        --collection-group=odin_runs \
        --field-config field-path=project_id,order=ascending \
        --field-config field-path=created_at,order=descending \
        --project=$PROJECT_ID || echo "Index already exists"
    
    # Create composite index for receipts (trace_id, timestamp asc)
    gcloud firestore indexes composite create \
        --collection-group=odin_receipts \
        --field-config field-path=trace_id,order=ascending \
        --field-config field-path=timestamp,order=ascending \
        --project=$PROJECT_ID || echo "Index already exists"
    
    echo "Firestore indexes created"
}

# Function to upload default realm pack
upload_realm_pack() {
    echo "Uploading default realm pack..."
    
    # Create a minimal business realm pack
    cat > /tmp/business-realm.json << EOF
{
  "realm": "business",
  "version": "0.9.0",
  "description": "Business processing realm",
  "sft_maps": {
    "invoice_to_iso20022": {
      "from_sft": "invoice_json",
      "to_sft": "iso20022_pain001",
      "intents": {
        "transform": {
          "description": "Transform invoice to ISO 20022 payment instruction"
        }
      },
      "fields": {},
      "const": {},
      "drop": []
    }
  },
  "validators": [
    "iban_checksum",
    "bic_format",
    "iso4217_currency"
  ],
  "policies": {
    "max_amount": 1000000,
    "approval_threshold": 10000,
    "high_risk_countries": ["XX", "YY"]
  }
}
EOF
    
    # Create tarball
    cd /tmp
    tar -czf business-0.9.0.tgz business-realm.json
    
    # Upload to GCS
    gsutil cp business-0.9.0.tgz gs://$PROJECT_ID-realm-packs/realms/ || echo "Upload failed"
    
    echo "Realm pack uploaded"
}

# Function to create default admin agent
create_admin_agent() {
    echo "Creating default admin agent..."
    
    # This would typically be done via the Gateway API
    # For now, we'll just log that it should be done
    echo "TODO: Create admin agent via /v1/admin/agents endpoint"
}

# Run initialization if in Cloud Run
if [ "$K_SERVICE" ]; then
    echo "Running in Cloud Run, performing initialization..."
    
    # Check if we have the necessary permissions
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "gserviceaccount.com"; then
        echo "Service account authenticated"
        
        # Only run these on first deployment
        if [ "$_ODIN_INIT" = "true" ]; then
            create_indexes
            upload_realm_pack
            create_admin_agent
        fi
    else
        echo "No service account found, skipping initialization"
    fi
fi

echo "Startup script complete"
