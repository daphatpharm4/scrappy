output "resource_group" { value = azurerm_resource_group.this.name }
output "aks_name" { value = module.aks.name }
output "aks_oidc_issuer_url" { value = module.aks.oidc_issuer_url }
output "keyvault_name" { value = module.keyvault.name }
output "storage_account_name" { value = module.storage.name }
output "storage_container_name" { value = module.storage.container_name }
output "acr_login_server" { value = module.acr.login_server }
output "query_api_client_id" { value = azurerm_user_assigned_identity.query_api.client_id }
output "ai_qa_client_id" { value = azurerm_user_assigned_identity.ai_qa.client_id }
output "pipeline_client_id" { value = azurerm_user_assigned_identity.pipeline.client_id }

output "kubeconfig_command" {
  value = "az aks get-credentials --resource-group ${azurerm_resource_group.this.name} --name ${module.aks.name} --overwrite-existing"
}
