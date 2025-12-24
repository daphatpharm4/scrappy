#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AZ_SUBSCRIPTION_ID:-}" ]]; then
  echo "AZ_SUBSCRIPTION_ID env var required" && exit 1
fi

az account set --subscription "$AZ_SUBSCRIPTION_ID"
az configure --defaults group="" location="" && true

echo "Logged in and subscription set"
