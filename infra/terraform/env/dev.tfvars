subscription_id    = "<your-subscription-id>"
tenant_id          = "<your-tenant-id>"
location           = "eastus"
environment        = "dev"
project            = "adl"
resource_group_name = "adl-dev-rg"
node_count         = 2
node_vm_size       = "Standard_DS2_v2"
kubernetes_version = null

tags = {
  project = "adl"
  env     = "dev"
  owner   = "platform"
}

aad_admin_object_ids = []
