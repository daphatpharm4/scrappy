#!/usr/bin/env bash
set -euo pipefail

: "${AZ_SUBSCRIPTION_ID:?Must set AZ_SUBSCRIPTION_ID}"
: "${ACR_NAME:?Must set ACR_NAME (e.g., adlacr)}"
: "${REGISTRY:?Must set REGISTRY (e.g., adlacr.azurecr.io)}"

IMAGES=(
  "query-api-service"
  "ai-qa-service"
  "pipeline-runner"
)

az account set --subscription "$AZ_SUBSCRIPTION_ID"

for IMAGE in "${IMAGES[@]}"; do
  if [[ -f "${IMAGE}/Dockerfile" ]]; then
    echo "Building $IMAGE"
    docker build -t "$REGISTRY/$IMAGE:latest" "$IMAGE"
    az acr login --name "$ACR_NAME"
    docker push "$REGISTRY/$IMAGE:latest"
  else
    echo "Skipping build for $IMAGE (Dockerfile not found)"
  fi
done

echo "Images handled"
