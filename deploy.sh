#!/bin/bash

set -e  # Exit on error

echo "🔨 Building image in Cloud Build..."
gcloud builds submit --tag gcr.io/facturacion-484614/api-facturas

echo "🚀 Deploying to Cloud Run with optimized settings..."
gcloud run deploy api-facturas \
  --image gcr.io/facturacion-484614/api-facturas \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800 \
  --concurrency 1 \
  --max-instances 10 \
  --port 8080 \
  --service-account api-facturas@facturacion-484614.iam.gserviceaccount.com \
  --set-env-vars "\
GOOGLE_CLOUD_PROJECT=facturacion-484614,\
GEMINI_LOCATION=us-central1,\
GEMINI_MODEL=gemini-2.5-flash-lite,\
MAX_FILE_SIZE_MB=300,\
GEMINI_CONCURRENCY_LIMIT=2,\
GEMINI_TIMEOUT_SECONDS=30,\
DEBUG=false"

echo "✅ Deployment completed!"
echo "📍 Service URL:"
gcloud run services describe api-facturas \
  --region us-central1 \
  --format 'value(status.url)'
