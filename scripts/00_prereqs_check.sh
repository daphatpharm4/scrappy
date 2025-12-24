#!/usr/bin/env bash
set -euo pipefail

command -v az >/dev/null 2>&1 || { echo "az CLI not found"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "terraform not found"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "helm not found"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq not found"; exit 1; }

echo "Prereqs OK"
