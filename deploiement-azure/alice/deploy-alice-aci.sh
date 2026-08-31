#!/usr/bin/env bash
# =====================================================================
# ALICE sur Azure : Container Instance + Database for PostgreSQL Flexible.
# Cerveau : Azure OpenAI (tourdecontrole, deployment ALICE_BRAIN_DEPLOYMENT).
# Image : construite dans le cloud via Azure Container Registry (pas de
#         docker local requis : az acr build).
#
# Usage : bash deploy-alice-aci.sh <RG> [LIEU=eastus] [TAG=alice:latest]
# Prérequis : az login OK (tenant/subscription actifs), crédits activés,
#             AZURE_OPENAI_KEY + ALICE_DB_PASSWORD exportées, deployment
#             Azure OpenAI créé (gpt-5-mini).
# =====================================================================
set -euo pipefail

RG="${1:?usage: bash deploy-alice-aci.sh <RG> [LIEU] [TAG]}"
LIEU="${2:-eastus}"
TAG="${3:-alice:latest}"
PG_NAME="alice-pg-${RG,,}"
PG_ADMIN="${ALICE_DB_USER:-alice}"
PG_PASSWORD="${ALICE_DB_PASSWORD:?exportez ALICE_DB_PASSWORD}"
SERVEUR_POSTGRES="$PG_NAME.postgres.database.azure.com"
VAULT="kv-$(echo -n "${RG}" | md5sum | cut -c1-12)"
REGISTRY="acralice${RG,,}"
REGISTRY="${REGISTRY//-/}"
CONTEXTE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> 1. groupe de ressources (existant toléré — les ressources ont leur propre région)"
az group create --name "$RG" --location "$LIEU" >/dev/null 2>&1 || true

echo "==> 2. Key Vault : clé du cerveau (Azure OpenAI, ref. de secours pour l'opérateur)"
az keyvault create --name "$VAULT" --resource-group "$RG" --location "$LIEU" 2>/dev/null || true
az keyvault secret set --vault-name "$VAULT" \
  --name "alice-brain-api-key" --value "${AZURE_OPENAI_KEY:?exportez AZURE_OPENAI_KEY}" \
  >/dev/null 2>&1 || true
echo "    (secret 'alice-brain-api-key' dans ${VAULT}.vault.azure.net)"

echo "==> 3. PostgreSQL Flexible (persistance de la table knowledge)"
if ! az postgres flexible-server show --name "$PG_NAME" --resource-group "$RG" >/dev/null 2>&1; then
  az postgres flexible-server create \
    --name "$PG_NAME" --resource-group "$RG" --location "$LIEU" \
    --admin-user "$PG_ADMIN" --admin-password "$PG_PASSWORD" \
    --sku-name Standard_B1ms --tier Burstable --storage-size 32 \
    --public-access All --yes
fi
# Règle de pare-feu ouverte : ⚠️ Action manuelle — pour un axe démo/hackathon.
# Restreindre production : --public-access <IP> ou VNet/private.
az postgres flexible-server firewall-rule create \
  --name "$PG_NAME" --resource-group "$RG" \
  --rule-name allow-all --start-ip-address 0.0.0.0 --end-ip-address 255.255.255.255 \
  2>/dev/null || true

# Base dédiée à ALICE
az postgres flexible-server db create \
  --server-name "$PG_NAME" --resource-group "$RG" \
  --database-name alice 2>/dev/null || true

echo "==> 4. build de l'image dans le cloud (ACR)"
az acr create --name "$REGISTRY" --resource-group "$RG" --location "$LIEU" \
  --sku Basic --admin-enabled 2>/dev/null || true
az acr build --registry "$REGISTRY" --resource-group "$RG" --image "$TAG" "$CONTEXTE"
REGISTRY_URL="${REGISTRY,,}.azurecr.io"
REGISTRY_USER="$(az acr credential show --name "$REGISTRY" --resource-group "$RG" --query 'usernames[0].value' -o tsv)"
REGISTRY_PASSWORD="$(az acr credential show --name "$REGISTRY" --resource-group "$RG" --query 'passwords[0].value' -o tsv)"

echo "==> 5. Container Instance (gate + ingest + UI)"
DB_URL="postgresql://${PG_ADMIN}:${PG_PASSWORD}@${SERVEUR_POSTGRES}:5432/alice"
KEY_B64="$(printf '%s' "${AZURE_OPENAI_KEY:?exportez AZURE_OPENAI_KEY}" | base64 -w0)"
az container create \
  --resource-group "$RG" \
  --name "alice-gate" \
  --image "${REGISTRY_URL}/${TAG}" \
  --cpu 1 --memory 1 --os-type Linux \
  --dns-name-label "alice${RG,,}" \
  --ports 8000 \
  --registry-login-server "$REGISTRY_URL" \
  --registry-username "$REGISTRY_USER" \
  --registry-password "$REGISTRY_PASSWORD" \
  --environment-variables \
    ALICE_BRAIN_AZURE="1" \
    ALICE_BRAIN_BASE="https://tourdecontrole.openai.azure.com/" \
    ALICE_BRAIN_DEPLOYMENT="${ALICE_BRAIN_DEPLOYMENT:-gpt-5-mini}" \
    ALICE_BRAIN_API_VERSION="${ALICE_BRAIN_API_VERSION:-2024-12-01-preview}" \
    ALICE_DB_URL="${DB_URL}" \
    ALICE_CARTE="/app/alicization/carte-vivante/cartes.json" \
    ALICE_DB="/tmp/alice/state/alice.db" \
  --secure-environment-variables \
    ALICE_BRAIN_API_KEY="$KEY_B64"

URL="http://$(az container show --resource-group "$RG" --name alice-gate \
  --query 'ipAddress.fqdn' -o tsv):8000"
echo "✔ ALICE en ligne : ${URL}"
echo "  → UI : ${URL}/   |   ingest : POST ${URL}/api/v1/ingest"
echo "  → Comparer local/cloud : bench_perf.py <LOCAL> ${URL} 20"
echo "  → Base knowledge persistante : ${DB_URL}"