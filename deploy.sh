#!/usr/bin/env bash
# Manpower Optimization — Build & Deploy to Azure App Service.
# Same pattern as Edwin: ship a ready-to-run zip, no server-side build.
#
# Usage: ./deploy.sh [--skip-build] [--skip-deploy]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SUBSCRIPTION="${AZURE_SUBSCRIPTION:-pzi-gxx1-sw5t3-dev001}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-manpower-pilot}"
APP_NAME="${AZURE_WEBAPP_NAME:-manpower-studio-3d85d5}"
ZIP_PATH="${DEPLOY_ZIP_PATH:-$ROOT/manpower-deploy.zip}"

SKIP_BUILD=false
SKIP_DEPLOY=false

for arg in "$@"; do
  case "$arg" in
    --skip-build)  SKIP_BUILD=true ;;
    --skip-deploy) SKIP_DEPLOY=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

echo "=== Manpower Optimization — Build & Deploy ==="

if [ "$SKIP_BUILD" = false ]; then
  echo ""
  echo "[1/2] Building deployment package..."
  OUTPUT_ZIP="$ZIP_PATH" bash "$ROOT/packaging/azure/build-deploy-zip.sh"
fi

if [ "$SKIP_DEPLOY" = false ]; then
  if [ ! -f "$ZIP_PATH" ]; then
    echo "Error: deployment package not found at $ZIP_PATH. Run without --skip-build first."
    exit 1
  fi

  echo ""
  echo "[2/2] Deploying to Azure App Service: $APP_NAME..."
  echo "Setting Azure subscription: $SUBSCRIPTION"
  az account set --subscription "$SUBSCRIPTION"

  BUILD_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
  az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --settings BUILD_ID="$BUILD_ID" \
    --output none 2>/dev/null || true

  az webapp deploy \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --src-path "$ZIP_PATH" \
    --type zip \
    --clean true \
    --restart true \
    --async true

  echo ""
  echo "Deployment complete!"
  echo "URL: https://${APP_NAME}.azurewebsites.net/"
fi
