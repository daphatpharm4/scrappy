#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  echo "Copied .env.example to .env"
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

echo "Starting services..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Bootstrapping MinIO prefixes..."
docker compose -f "$COMPOSE_FILE" run --rm ingestion-service python /app/scripts/bootstrap_minio.py

echo "Running ingestion..."
docker compose -f "$COMPOSE_FILE" run --rm ingestion-service python /app/ingestion-service/ingestion_service.py run

echo "Running cleaning..."
docker compose -f "$COMPOSE_FILE" run --rm cleaning-service python /app/cleaning-service/cleaning_service.py run

echo "Query API sample call..."
curl -s -H "Authorization: Bearer $(grep SHARED_BEARER_TOKEN "$ENV_FILE" | cut -d'=' -f2)" "http://localhost:${QUERY_API_PORT:-8000}/analytics/average_price?country=kenya" | jq .

echo "AI Q&A sample call..."
curl -s -X POST -H "Content-Type: application/json" -d '{"question":"What is the average price of maize in Kenya?","country":"kenya","item":"maize"}' "http://localhost:${AI_QA_PORT:-8001}/ask" | jq .
