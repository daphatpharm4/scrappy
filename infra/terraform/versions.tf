terraform {
  required_version = ">= 1.6.0"

  backend "azurerm" {
    resource_group_name  = "adl-dev-rg"
    storage_account_name = "adltfstatesa"
    container_name       = "tfstate"
    key                  = "dev.terraform.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.107"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.48"
    }
  }
}
