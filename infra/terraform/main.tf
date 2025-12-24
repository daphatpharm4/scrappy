locals {
  name_prefix = "${var.project}-${var.environment}"
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

module "loganalytics" {
  source              = "./modules/loganalytics"
  name                = "${local.name_prefix}-law"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  retention_in_days   = 30
  tags                = var.tags
}

module "acr" {
  source              = "./modules/acr"
  name                = "${replace(local.name_prefix, "-", "") }acr"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "Basic"
  tags                = var.tags
}

module "storage" {
  source              = "./modules/storage"
  name                = "${replace(local.name_prefix, "-", "") }sa"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  container_name      = "datalake"
  tags                = var.tags
}

module "keyvault" {
  source                        = "./modules/keyvault"
  name                          = "${local.name_prefix}-kv"
  location                      = var.location
  resource_group_name           = azurerm_resource_group.this.name
  tenant_id                     = var.tenant_id
  enable_rbac_authorization     = true
  purge_protection_enabled      = false
  soft_delete_retention_days    = 7
  tags                          = var.tags
}

module "aks" {
  source                   = "./modules/aks"
  name                     = "${local.name_prefix}-aks"
  location                 = var.location
  resource_group_name      = azurerm_resource_group.this.name
  dns_prefix               = local.name_prefix
  node_count               = var.node_count
  node_vm_size             = var.node_vm_size
  kubernetes_version       = var.kubernetes_version
  log_analytics_workspace  = module.loganalytics.id
  aad_admin_object_ids     = var.aad_admin_object_ids
  tags                     = var.tags
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = module.acr.id
  role_definition_name = "AcrPull"
  principal_id         = module.aks.kubelet_identity_object_id
}

resource "azurerm_role_assignment" "aks_msi_acr_push" {
  scope                = module.acr.id
  role_definition_name = "AcrPush"
  principal_id         = module.aks.identity_principal_id
}

resource "azurerm_user_assigned_identity" "query_api" {
  name                = "${local.name_prefix}-queryapi-mi"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "ai_qa" {
  name                = "${local.name_prefix}-aiqa-mi"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "pipeline" {
  name                = "${local.name_prefix}-pipeline-mi"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = var.tags
}

locals {
  federated_subjects = {
    query_api = "system:serviceaccount:adl-platform:query-api-sa"
    ai_qa     = "system:serviceaccount:adl-platform:ai-qa-sa"
    pipeline  = "system:serviceaccount:adl-jobs:pipeline-sa"
  }
}

resource "azurerm_federated_identity_credential" "query_api" {
  name                = "${local.name_prefix}-queryapi-fic"
  resource_group_name = azurerm_resource_group.this.name
  parent_id           = azurerm_user_assigned_identity.query_api.id
  issuer              = module.aks.oidc_issuer_url
  subject             = local.federated_subjects.query_api
  audience            = ["api://AzureADTokenExchange"]
}

resource "azurerm_federated_identity_credential" "ai_qa" {
  name                = "${local.name_prefix}-aiqa-fic"
  resource_group_name = azurerm_resource_group.this.name
  parent_id           = azurerm_user_assigned_identity.ai_qa.id
  issuer              = module.aks.oidc_issuer_url
  subject             = local.federated_subjects.ai_qa
  audience            = ["api://AzureADTokenExchange"]
}

resource "azurerm_federated_identity_credential" "pipeline" {
  name                = "${local.name_prefix}-pipeline-fic"
  resource_group_name = azurerm_resource_group.this.name
  parent_id           = azurerm_user_assigned_identity.pipeline.id
  issuer              = module.aks.oidc_issuer_url
  subject             = local.federated_subjects.pipeline
  audience            = ["api://AzureADTokenExchange"]
}

resource "azurerm_role_assignment" "query_api_kv" {
  scope                = module.keyvault.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.query_api.principal_id
}

resource "azurerm_role_assignment" "ai_qa_kv" {
  scope                = module.keyvault.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ai_qa.principal_id
}

resource "azurerm_role_assignment" "pipeline_kv" {
  scope                = module.keyvault.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
}

resource "azurerm_role_assignment" "query_api_storage" {
  scope                = module.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.query_api.principal_id
}

resource "azurerm_role_assignment" "ai_qa_storage" {
  scope                = module.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.ai_qa.principal_id
}

resource "azurerm_role_assignment" "pipeline_storage" {
  scope                = module.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.pipeline.principal_id
}

output "resource_group" {
  value = azurerm_resource_group.this.name
}

output "aks_name" {
  value = module.aks.name
}

output "aks_oidc_issuer_url" {
  value = module.aks.oidc_issuer_url
}

output "keyvault_name" {
  value = module.keyvault.name
}

output "storage_account_name" {
  value = module.storage.name
}

output "storage_container_name" {
  value = module.storage.container_name
}

output "acr_login_server" {
  value = module.acr.login_server
}

output "query_api_client_id" {
  value = azurerm_user_assigned_identity.query_api.client_id
}

output "ai_qa_client_id" {
  value = azurerm_user_assigned_identity.ai_qa.client_id
}

output "pipeline_client_id" {
  value = azurerm_user_assigned_identity.pipeline.client_id
}
