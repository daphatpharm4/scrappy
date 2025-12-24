#!/usr/bin/env bash
set -euo pipefail

: "${AZ_SUBSCRIPTION_ID:?Must set AZ_SUBSCRIPTION_ID}"
: "${RESOURCE_GROUP:?Must set RESOURCE_GROUP}"
: "${AKS_NAME:?Must set AKS_NAME}"

az account set --subscription "$AZ_SUBSCRIPTION_ID"

# Install Secrets Store CSI Driver and Azure Key Vault Provider
helm repo add csi-secrets-store https://azure.github.io/secrets-store-csi-driver-provider-azure/charts
helm repo update
kubectl create namespace kube-system >/dev/null 2>&1 || true
helm upgrade --install csi-secrets-store csi-secrets-store/secrets-store-csi-driver \
  --namespace kube-system \
  --set linux.enabled=true \
  --set windows.enabled=false \
  --set secrets-store-csi-driver.enableSecretRotation=true
helm upgrade --install csi-secrets-store-provider-azure csi-secrets-store/csi-secrets-store-provider-azure \
  --namespace kube-system

# Enable Workload Identity add-on components if needed
az aks update --resource-group "$RESOURCE_GROUP" --name "$AKS_NAME" --enable-oidc-issuer --enable-workload-identity

echo "CSI driver and Workload Identity ensured"
