#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TF_DIR="$ROOT_DIR/infra/terraform"
TF_VARS_FILE="$TF_DIR/env/dev.tfvars"

cd "$TF_DIR"
terraform destroy -auto-approve -var-file="$TF_VARS_FILE"
