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
  DOCKERFILE="${IMAGE}/Dockerfile"
  if [[ ! -f "$DOCKERFILE" ]]; then
    echo "Skipping build for $IMAGE (Dockerfile not found)"
    continue
  fi

  echo "Building $IMAGE with context '.' and Dockerfile $DOCKERFILE"
  docker build -t "$REGISTRY/$IMAGE:latest" -f "$DOCKERFILE" .
  az acr login --name "$ACR_NAME"
  docker push "$REGISTRY/$IMAGE:latest"
done

echo "Images handled"
