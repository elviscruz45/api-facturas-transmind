#!/bin/bash

# ============================================================
#  deploy_gcp.sh — Deploy rápido e integral a GCP Cloud Run
#  Lee variables desde .env y las inyecta al servicio.
# ============================================================

set -euo pipefail

# ── Colores ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log()    { echo -e "${CYAN}[deploy]${NC} $*"; }
success(){ echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Configuración del proyecto ────────────────────────────────
PROJECT_ID="facturacion-484614"
SERVICE_NAME="api-facturas"
REGION="us-central1"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
SERVICE_ACCOUNT="${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
ENV_FILE="${ENV_FILE:-.env}"   # permite: ENV_FILE=.env.prod ./deploy_gcp.sh

# ── Validaciones previas ──────────────────────────────────────
echo -e "\n${BOLD}══════════════════════════════════════════${NC}"
echo -e "${BOLD}  🚀 Deploy → Cloud Run  |  ${SERVICE_NAME}${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}\n"

command -v gcloud >/dev/null 2>&1 || error "gcloud CLI no encontrado. Instálalo: https://cloud.google.com/sdk"

if [[ ! -f "$ENV_FILE" ]]; then
  error "Archivo $ENV_FILE no encontrado. Crea uno basado en .env.template"
fi

# ── Leer y construir --set-env-vars ──────────────────────────
log "Leyendo variables de entorno desde ${ENV_FILE}..."

ENV_VARS=""
# Variables que NO deben enviarse a Cloud Run (gestión local / sustituidas por IAM)
SKIP_VARS=("GOOGLE_APPLICATION_CREDENTIALS" "NAME_SUPABASE_PROJECT" "DB_PASSWORD")

while IFS= read -r line || [[ -n "$line" ]]; do
  # Ignorar líneas vacías y comentarios
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # Separar clave y valor
  key="${line%%=*}"
  value="${line#*=}"

  # Limpiar espacios del key
  key="$(echo "$key" | xargs)"
  [[ -z "$key" ]] && continue

  # Saltar variables de la lista negra
  skip=false
  for skip_var in "${SKIP_VARS[@]}"; do
    [[ "$key" == "$skip_var" ]] && skip=true && break
  done
  $skip && warn "Saltando variable ${key} (no aplica en Cloud Run)" && continue

  # Escapar comas en el valor (gcloud usa , como separador)
  value="${value//,/\\,}"
  # Quitar comillas envolventes si las hay
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  if [[ -n "$ENV_VARS" ]]; then
    ENV_VARS="${ENV_VARS},${key}=${value}"
  else
    ENV_VARS="${key}=${value}"
  fi
done < "$ENV_FILE"

if [[ -z "$ENV_VARS" ]]; then
  error "No se encontraron variables válidas en $ENV_FILE"
fi

VAR_COUNT=$(echo "$ENV_VARS" | tr ',' '\n' | wc -l | xargs)
success "${VAR_COUNT} variables de entorno cargadas"

# ── Confirmar proyecto activo ─────────────────────────────────
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
  log "Cambiando proyecto activo a ${PROJECT_ID}..."
  gcloud config set project "$PROJECT_ID"
fi

# ── Build con Cloud Build ─────────────────────────────────────
echo ""
log "Construyendo imagen con Cloud Build..."
log "  → ${IMAGE}:latest"

gcloud builds submit \
  --tag "${IMAGE}:latest" \
  --project "$PROJECT_ID" \
  .

success "Imagen construida y publicada en Container Registry"

# ── Deploy a Cloud Run ────────────────────────────────────────
echo ""
log "Desplegando en Cloud Run [${REGION}]..."

gcloud run deploy "$SERVICE_NAME" \
  --image "${IMAGE}:latest" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800 \
  --concurrency 10 \
  --max-instances 10 \
  --port 8080 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "$ENV_VARS" \
  --project "$PROJECT_ID"

# ── Resultado ─────────────────────────────────────────────────
echo ""
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format 'value(status.url)' 2>/dev/null || echo "")

echo -e "\n${BOLD}══════════════════════════════════════════${NC}"
success "Despliegue completado exitosamente"
if [[ -n "$SERVICE_URL" ]]; then
  echo -e "${GREEN}🌐 URL:${NC} ${SERVICE_URL}"
  echo -e "${GREEN}🔍 Health:${NC} ${SERVICE_URL}/health"
  echo -e "${GREEN}📄 Docs:${NC}  ${SERVICE_URL}/docs"
fi
echo -e "${BOLD}══════════════════════════════════════════${NC}\n"
