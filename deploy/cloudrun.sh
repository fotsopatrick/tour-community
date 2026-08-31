#!/bin/bash
# Deploiement de la Tour Community sur Google Cloud : Cloud Run + Cloud SQL.
#
# Prérequis :
#   - gcloud installe et les credits hackathon actives (150 $)
#   - un fichier de compte de service : SERVICE_ACCOUNT_JSON (chemin)
#   - vos propres mots de passe, passes en variables d'environnement :
#       export PGPASSWORD='...' ODOO_ADMIN_PASSWD='...' GEMINI_KEY='...' WEBMCP_KEY='...'
#
# Usage :
#   source deploy/cloudrun.sh PROPRIETAIRE  # ex: fotsopatrick
#
# Ce script est le « circuit » de deploiement, pensé pour être rejoué tel quel.
set -euo pipefail

PROJET="${1:?Usage: cloudrun.sh <projet_gcp>}"
SERVICE="${2:-tour-community}"
REGION="${3:-europe-west1}"
INSTANCE_SQL="${4:-tour-postgres}"
IMAGE="gcr.io/${PROJET}/${SERVICE}"

echo "==> 1. Identification (compte de service)"
gcloud auth activate-service-account --key-file="${SERVICE_ACCOUNT_JSON:?posez SERVICE_ACCOUNT_JSON}"
gcloud config set project "${PROJET}"
gcloud config set run/region "${REGION}"

echo "==> 2. Cloud SQL : instance Postgres (creer si absente)"
if ! gcloud sql instances describe "${INSTANCE_SQL}" >/dev/null 2>&1; then
  gcloud sql instances create "${INSTANCE_SQL}" \
    --database-version=POSTGRES_15 --cpu=1 --memory=4GB \
    --region="${REGION}" --root-password="${PGROOT_PASSWORD:?posez PGROOT_PASSWORD}"
fi
# Base et utilisateur Odoo
gcloud sql databases create tour_prod --instance="${INSTANCE_SQL}" 2>/dev/null || true
gcloud sql users create odoo --instance="${INSTANCE_SQL}" --password="${PGPASSWORD:?posez PGPASSWORD}" 2>/dev/null || true
gcloud sql users set-password odoo --instance="${INSTANCE_SQL}" --password="${PGPASSWORD}"

echo "==> 3. Image : build + submit"
gcloud builds submit --tag "${IMAGE}" --timeout=1800 --ignore-file=deploy/.gcloudignore .

echo "==> 4. Cloud Run : deploy (proxy Cloud SQL automatique)"
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 2 \
  --timeout 300 \
  --concurrency 8 \
  --add-cloudsql-instances "${PROJET}:${REGION}:${INSTANCE_SQL}" \
  --set-env-vars "PGHOST=127.0.0.1,PGPORT=5432,PGUSER=odoo,PGPASSWORD=${PGPASSWORD},PGDATABASE=tour_prod,ODOO_ADMIN_PASSWD=${ODOO_ADMIN_PASSWD}"

URL=$(gcloud run services describe "${SERVICE}" --region "${REGION}" --format='value(status.url)')
echo "==> 5. URL : ${URL}"
echo "    Login : admin / ${ODOO_ADMIN_PASSWD}  |  MCP : ${URL}/mcp/tour (Bearer ${WEBMCP_KEY})"

echo "==> 6. (Option) Clés de la Tour sur l'instance distante :"
echo "    Passez dans Réglages > WebMCP : clé Gemini, clé WebMCP, moteurs."
echo "    OU deposez les parametres via un odoo shell apres premier demarrage."

echo "CIRCUIT OK : ${SERVICE} deploie."