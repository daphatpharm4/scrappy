variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g., dev)"
  type        = string
  default     = "dev"
}

variable "project" {
  description = "Project prefix"
  type        = string
  default     = "adl"
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "node_count" {
  description = "Default node count for the system pool"
  type        = number
  default     = 2
}

variable "node_vm_size" {
  description = "VM size for AKS nodes"
  type        = string
  default     = "Standard_DS2_v2"
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version (leave null for default)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}

variable "aad_admin_object_ids" {
  description = "List of AAD object IDs to assign as cluster admins"
  type        = list(string)
  default     = []
}
