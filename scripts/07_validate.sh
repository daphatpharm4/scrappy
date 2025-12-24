#!/usr/bin/env bash
set -euo pipefail

: "${INGRESS_NAMESPACE:=adl-platform}"
: "${HOST:?Must set HOST for curl tests}"
: "${API_AUTH_TOKEN:?Must set API_AUTH_TOKEN for auth tests}"

kubectl get pods -A
kubectl get ingress -n "$INGRESS_NAMESPACE"

# wait for ingress IP
for i in {1..30}; do
  ADDR=$(kubectl get ingress -n "$INGRESS_NAMESPACE" -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' || true)
  [[ -n "$ADDR" ]] && break
  echo "Waiting for ingress IP..." && sleep 10
done

echo "Ingress Address: ${ADDR:-not-ready}"

curl -k -H "Authorization: Bearer $API_AUTH_TOKEN" "https://${HOST}/api/health" || true
curl -k -H "Authorization: Bearer $API_AUTH_TOKEN" "https://${HOST}/ask/health" || true

kubectl get cronjob -n adl-jobs
