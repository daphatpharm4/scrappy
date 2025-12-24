#!/usr/bin/env bash
set -euo pipefail

: "${AZ_SUBSCRIPTION_ID:?Must set AZ_SUBSCRIPTION_ID}"
: "${RESOURCE_GROUP:?Must set RESOURCE_GROUP}"
: "${AKS_NAME:?Must set AKS_NAME}"

az account set --subscription "$AZ_SUBSCRIPTION_ID"
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$AKS_NAME" --overwrite-existing

echo "kubectl configured"
