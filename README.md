# African Data Layer on AKS

Production-quality, minimal-cost foundation to deploy the African Data Layer microservices to Azure Kubernetes Service (AKS) with Azure Blob Storage as the data lake and Azure Key Vault for secrets via Workload Identity + Secrets Store CSI Driver.

This repository now includes lightweight placeholder implementations for the three services (`query-api-service`, `ai-qa-service`, and `pipeline-runner`) so you can build/push images and validate the deployment scaffolding end-to-end.

## Prerequisites
- Azure subscription with Owner role on the target resource group scope
- Azure Cloud Shell (recommended) or local shell with: `az` CLI, Terraform >= 1.6, kubectl, helm, jq, make
- Sufficient quota for AKS, ACR, Storage, Key Vault, Log Analytics
- Container images available for `query-api-service`, `ai-qa-service`, and `pipeline-runner` (or Dockerfiles to build)

## Quickstart (Azure Cloud Shell)
1. Clone this repo and enter it.
2. Review and update `infra/terraform/env/dev.tfvars` and `k8s/env/values-dev.yaml` with your subscription ID, region, DNS host, and image tags.
3. Run the scripts in order (or use `make all`):
   - `scripts/00_prereqs_check.sh`
   - `scripts/01_bootstrap_login.sh`
   - `scripts/02_provision_infra.sh`
   - `scripts/03_build_and_push_images.sh` (optional if images already exist)
   - `scripts/04_connect_kubectl.sh`
   - `scripts/05_install_csi_workload_identity.sh`
   - `scripts/06_deploy_apps.sh`
   - `scripts/07_validate.sh`
4. Access the services (HTTP or HTTPS depending on your ingress/TLS settings):
   - Query API: `curl -H "Authorization: Bearer <API_AUTH_TOKEN>" https://<host>/api/health`
   - AI QA: `curl -H "Authorization: Bearer <API_AUTH_TOKEN>" https://<host>/ask/health`

## Configuration
- `k8s/env/values-dev.yaml`:
  - `global.azure.*`: subscription, tenant, region, resource names
  - `global.azure.queryApiClientId`, `aiQaClientId`, `pipelineClientId`: workload identity client IDs from Terraform outputs
  - `global.images.*`: registry and tags for query-api, ai-qa, pipeline
  - `global.ingress.host` / `global.ingress.tlsSecretName`: DNS and TLS
  - `queryApi.apiAuthSecretName`: must match Key Vault secret `API_AUTH_TOKEN`
  - `aiQa.queryApiUrl`: internal service URL (e.g., `http://query-api.adl-platform.svc.cluster.local:8000`)
  - Storage: `global.storageAccount`, `global.blobContainer`, prefixes
  - Pipeline schedule: `pipeline.schedule`
- `k8s/env/datasets.yaml`: datasets config mounted to the pipeline CronJob
- `infra/terraform/env/dev.tfvars`: project prefix, environment, region, node pool sizing, resource tags, AAD tenant and subscription IDs
- Create Key Vault secret `API_AUTH_TOKEN` with the bearer token needed by `query-api-service`.
- For the scraper-service, set Key Vault secrets for `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `HTTP_PROXY`, and `HTTPS_PROXY` as needed.
- Configure scraper targets and model provider in `k8s/env/values-dev.yaml` under the `scraper` section. The CronJob mounts `targets.txt` from a ConfigMap and selects the provider via `SCRAPER_MODEL_PROVIDER` (openai/deepseek/xai).

## Testing Endpoints
```bash
API_AUTH_TOKEN=<token>
HOST=<ingress-host>
curl -H "Authorization: Bearer ${API_AUTH_TOKEN}" https://${HOST}/api/health
curl -H "Authorization: Bearer ${API_AUTH_TOKEN}" https://${HOST}/ask/health
```

## Observability
- Azure Monitor / Container Insights is enabled via Log Analytics
- Readiness and liveness probes on `/health`
- HPAs on query-api and ai-qa (CPU-based)
- Basic alert templates are in Helm values for extension
- Scraper CronJob for automated lead extraction using LLM summarization

## Data Lake Access
- Data is stored in the blob container `datalake` in the provisioned Storage Account.
- Use `az storage blob list --account-name <storage> -c datalake` after authenticating with `az login` and `az account set`.

## Troubleshooting
- **Pods Pending**: check node quotas and `kubectl describe pod`. Verify CSI Driver and Workload Identity installation.
- **Auth Failures**: ensure Key Vault secret `API_AUTH_TOKEN` exists and federated credentials are created; rerun `scripts/05_install_csi_workload_identity.sh`.
- **Ingress Issues**: confirm DNS points to the ingress public IP from `kubectl get ingress -n adl-platform`.
- **Terraform Errors**: validate `dev.tfvars` values and that the user has rights to create resources.

## Cleanup
Run `scripts/99_destroy.sh` to remove provisioned resources.

## Remote Terraform State
- Create (or reuse) a storage account and container for state, for example:
  - Resource group: `adl-dev-rg`
  - Storage account: `adltfstatesa`
  - Container: `tfstate`
  - Key: `dev.terraform.tfstate`
- The Terraform backend is configured in `infra/terraform/versions.tf`; override any of these values at init time with `-backend-config` if you use different names.
- When running in CI (see `.github/workflows/azure-deploy.yaml`), set secrets for:
  - `TFSTATE_RESOURCE_GROUP`, `TFSTATE_STORAGE_ACCOUNT`, `TFSTATE_CONTAINER`, and optionally `TFSTATE_KEY` (default `dev.terraform.tfstate`).
  - `AZURE_CREDENTIALS`, `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `RESOURCE_GROUP`, `AKS_CLUSTER_NAME`, `ACR_NAME`, `ACR_LOGIN_SERVER`, and the workload identity client IDs for `queryApi`, `aiQa`, and `pipeline`.
