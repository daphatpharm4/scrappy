variable "name" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "dns_prefix" { type = string }
variable "node_count" { type = number }
variable "node_vm_size" { type = string }
variable "kubernetes_version" {
  type    = string
  default = null
}
variable "log_analytics_workspace" { type = string }
variable "aad_admin_object_ids" { type = list(string) }
variable "tags" { type = map(string) }
