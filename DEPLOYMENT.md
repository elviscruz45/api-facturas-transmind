# Deployment Guide - API Facturas

## Local Development with Docker

### Build and run locally

```bash
# Build the image
docker build -t api-facturas:local .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Test locally

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/info
```

## Deploy to Google Cloud Run

### Prerequisites

1. Install Google Cloud SDK

```bash
# macOS
brew install google-cloud-sdk

# Or download from https://cloud.google.com/sdk/docs/install
```

2. Authenticate

```bash
gcloud auth login
gcloud config set project facturacion-484614
```

3. Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com
```

4. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create api-facturas \
  --display-name="API Facturas Service Account"

# Grant necessary roles
gcloud projects add-iam-policy-binding facturacion-484614 \
  --member="serviceAccount:api-facturas@facturacion-484614.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding facturacion-484614 \
  --member="serviceAccount:api-facturas@facturacion-484614.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

### Option 1: Manual Deployment

```bash
# Set variables
export PROJECT_ID=facturacion-484614
export REGION=us-central1
export SERVICE_NAME=api-facturas

# Build and push to Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800 \
  --concurrency 10 \
  --max-instances 10 \
  --service-account api-facturas@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GEMINI_LOCATION=$REGION
```

### Option 2: Automatic Deployment with Cloud Build

```bash
# Submit build (uses cloudbuild.yaml)
gcloud builds submit --config cloudbuild.yaml
```

### Option 3: Continuous Deployment from GitHub

```bash
# Connect your GitHub repo
gcloud run services update-traffic $SERVICE_NAME --to-latest

# Set up Cloud Build trigger
gcloud beta builds triggers create github \
  --repo-name=api-facturas \
  --repo-owner=YOUR_GITHUB_USERNAME \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

## Configuration

### Environment Variables (Cloud Run)

Set via console or CLI:

```bash
gcloud run services update api-facturas \
  --region us-central1 \
  --set-env-vars \
GOOGLE_CLOUD_PROJECT=facturacion-484614,\
GEMINI_MODEL=gemini-2.5-flash-lite,\
GEMINI_LOCATION=us-central1,\
MAX_FILE_SIZE_MB=300
```

### Secrets (Optional - for sensitive data)

```bash
# Create secret
echo -n "secret-value" | gcloud secrets create my-secret --data-file=-

# Grant access to service account
gcloud secrets add-iam-policy-binding my-secret \
  --member="serviceAccount:api-facturas@facturacion-484614.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Mount in Cloud Run
gcloud run services update api-facturas \
  --update-secrets=/secrets/my-secret=my-secret:latest
```

## Verify Deployment

```bash
# Get service URL
gcloud run services describe api-facturas --region us-central1 --format='value(status.url)'

# Test endpoints
export SERVICE_URL=$(gcloud run services describe api-facturas --region us-central1 --format='value(status.url)')

curl $SERVICE_URL/health
curl $SERVICE_URL/api/v1/info
```

## Monitoring

```bash
# View logs
gcloud run services logs read api-facturas --region us-central1 --limit 50

# Follow logs (live)
gcloud run services logs tail api-facturas --region us-central1

# View in Cloud Console
echo "https://console.cloud.google.com/run/detail/us-central1/api-facturas/logs?project=facturacion-484614"
```

## Troubleshooting

### Check service status

```bash
gcloud run services describe api-facturas --region us-central1
```

### Test locally with Cloud Run emulator

```bash
docker build -t api-facturas:test .
docker run -p 8080:8080 \
  -e GOOGLE_CLOUD_PROJECT=facturacion-484614 \
  api-facturas:test
```

### Debug startup issues

```bash
# Run container locally and check logs
docker run --rm api-facturas:test

# Exec into running container
docker exec -it api-facturas /bin/bash
```

## Cost Optimization

- Use `--min-instances 0` for development (default)
- Set `--max-instances` based on expected load
- Monitor usage: https://console.cloud.google.com/run/detail/us-central1/api-facturas/metrics

## Security Best Practices

1. **Never include credentials in Docker image**
2. Use Service Account authentication (managed by Cloud Run)
3. Enable VPC connector for private resources if needed
4. Set up Cloud Armor for DDoS protection
5. Use Secret Manager for sensitive configuration
6. Review IAM permissions regularly

## Rollback

```bash
# List revisions
gcloud run revisions list --service api-facturas --region us-central1

# Rollback to previous revision
gcloud run services update-traffic api-facturas \
  --to-revisions REVISION_NAME=100 \
  --region us-central1
```
