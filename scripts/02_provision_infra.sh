#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TF_DIR="$ROOT_DIR/infra/terraform"
TF_VARS_FILE="$TF_DIR/env/dev.tfvars"

: "${AZ_SUBSCRIPTION_ID:?Must set AZ_SUBSCRIPTION_ID}"

az account set --subscription "$AZ_SUBSCRIPTION_ID"

cd "$TF_DIR"
terraform init
terraform apply -auto-approve -var-file="$TF_VARS_FILE"

terraform output
