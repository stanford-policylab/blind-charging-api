# NOTE
#
# Be sure to authenticate via the Azure CLI with the correct tenant before running Terraform.
#
#  > az cloud set -n AzureUSGovernment
#  > az login

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0.1"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 1.15.0"
    }
  }

  required_version = ">= 1.5.7"
}

provider "azurerm" {
  subscription_id = var.subscription_id
  environment     = var.azure_env

  features {
  }
}

provider "azapi" {
  tenant_id       = data.azurerm_client_config.current.tenant_id
  subscription_id = var.subscription_id
  environment     = var.azure_env
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "RaceBlindCharging"
  location = var.location
  tags     = var.tags
}
