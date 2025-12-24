#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VALUES_FILE="$ROOT_DIR/k8s/env/values-dev.yaml"

: "${HELM_RELEASE:=african-data-layer}"

kubectl create namespace adl-platform >/dev/null 2>&1 || true
kubectl create namespace adl-jobs >/dev/null 2>&1 || true

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.nodeSelector."kubernetes\.io/os"=linux \
  --set defaultBackend.nodeSelector."kubernetes\.io/os"=linux

helm upgrade --install "$HELM_RELEASE" "$ROOT_DIR/k8s/helm/african-data-layer" \
  --namespace adl-platform \
  --values "$VALUES_FILE"

echo "Helm release deployed"
