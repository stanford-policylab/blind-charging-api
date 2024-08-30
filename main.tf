# README
#
# In order to use Terraform with Azure, you will need to create a service account.
#
# You will also of course need the Azure CLI installed.
#
# For example, to create a GovCloud service account, run the following:
#
#  > az cloud set -n AzureUSGovernment
#  > az login
#
# You will need to insert the following information into your tfvars file:
#  > SUBSCRIPTION=$(az account show --query id -o tsv)
#  > TENANT_ID=$(az account show --query tenantId -o tsv)
#  > echo "Subscription: $SUBSCRIPTION"
#  > echo "TenantId: $TENANT_ID"
#
# Create the service account:
#  > az ad sp create-for-rbac -n Terraform --role Contributor --scopes /subscriptions/$SUBSCRIPTION

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

variable "tenant_id" {
  type = string
}

variable "subscription_id" {
  type = string
}

variable "partner" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "location" {
  type    = string
  default = "usgovvirginia"
}

variable "azure_env" {
  type    = string
  default = "usgovernment"
}

variable "ssh_pub_key" {
  type    = string
  default = "~/.ssh/id_rsa.pub"
}

variable "tags" {
  type = map(string)
  default = {
    "environment" = "production"
    "app"         = "raceblind"
  }
}

provider "azurerm" {
  tenant_id       = var.tenant_id
  subscription_id = var.subscription_id
  features {}
  environment = var.azure_env
}

provider "azapi" {
  tenant_id       = var.tenant_id
  subscription_id = var.subscription_id
  environment     = var.azure_env
}

resource "azurerm_resource_group" "main" {
  name     = "RaceBlindCharging"
  location = var.location
  tags     = var.tags
}

resource "azurerm_redis_cache" "main" {
  name                 = format("%s-rbc-redis", var.partner)
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  capacity             = 3
  family               = "C"
  sku_name             = "Standard"
  non_ssl_port_enabled = false
  tags                 = var.tags
}

resource "azurerm_mssql_server" "main" {
  name                         = format("%s-rbc-sql", var.partner)
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = "bcadmin"
  administrator_login_password = var.db_password
  tags                         = var.tags
}

resource "azurerm_mssql_database" "main" {
  name           = format("%s-rbc-db", var.partner)
  server_id      = azurerm_mssql_server.main.id
  collation      = "SQL_Latin1_General_CP1_CI_AS"
  max_size_gb    = 5
  sku_name       = "S0"
  zone_redundant = false
  tags           = var.tags
  enclave_type   = "VBS"
  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_virtual_network" "main" {
  name                = format("%s-rbc-vnet", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  address_space       = ["10.0.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "default" {
  name                 = "default"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.0.0/24"]
  service_endpoints    = ["Microsoft.CognitiveServices"]
}

resource "azurerm_cognitive_account" "main" {
  name                = format("%s-rbc-cognitive", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku_name            = "S0"
  kind                = "OpenAI"
  tags                = var.tags
}

# TODO(jnu): azurerm does not support the content filter resource yet.check "name"
# See https://github.com/hashicorp/terraform-provider-azurerm/issues/22822
resource "azapi_resource" "no_content_filter" {
  type                      = "Microsoft.CognitiveServices/accounts/raiPolicies@2023-10-01-preview"
  name                      = "NoFilter"
  parent_id                 = azurerm_cognitive_account.main.id
  schema_validation_enabled = false
  body = jsonencode({
    name = "NoFilter"
    properties = {
      basePolicyName = "Microsoft.Default"
      type           = "UserManaged"
      mode           = "Default"
      contentFilters = [
        { name = "hate", blocking = false, enabled = false, allowedContentLevel = "High", source = "Prompt" },
        { name = "sexual", blocking = false, enabled = false, allowedContentLevel = "High", source = "Prompt" },
        { name = "selfharm", blocking = false, enabled = false, allowedContentLevel = "High", source = "Prompt" },
        { name = "violence", blocking = false, enabled = false, allowedContentLevel = "High", source = "Prompt" },
        { name = "hate", blocking = false, enabled = false, allowedContentLevel = "High", source = "Completion" },
        { name = "sexual", blocking = false, enabled = false, allowedContentLevel = "High", source = "Completion" },
        { name = "selfharm", blocking = false, enabled = false, allowedContentLevel = "High", source = "Completion" },
        { name = "violence", blocking = false, enabled = false, allowedContentLevel = "High", source = "Completion" },
        { name = "jailbreak", blocking = false, enabled = false, allowedContentLevel = "High", source = "Prompt" },
        { name = "indirect_attack", blocking = false, enabled = false, source = "Completion" },
        { name = "protected_material_text", blocking = false, enabled = false, source = "Completion" },
      ]
    }
  })
  depends_on = [azurerm_cognitive_account.main]
}

resource "azurerm_cognitive_deployment" "main" {
  name                 = format("%s-rbc-cognitive-deployment", var.partner)
  cognitive_account_id = azurerm_cognitive_account.main.id
  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-05-13"
  }
  sku {
    name     = "Standard"
    tier     = "Standard"
    capacity = 80
  }
  rai_policy_name        = azapi_resource.no_content_filter.name
  version_upgrade_option = "NoAutoUpgrade"
}

resource "azurerm_private_endpoint" "mssql" {
  name                = format("%s-rbc-mssql-pe", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.default.id
  private_service_connection {
    name                           = "mssql-psc"
    private_connection_resource_id = azurerm_mssql_server.main.id
    subresource_names              = ["SqlServer"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_endpoint" "cognitive" {
  name                = format("%s-rbc-cognitive-pe", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.default.id
  private_service_connection {
    name                           = "cognitive-psc"
    private_connection_resource_id = azurerm_cognitive_account.main.id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_endpoint" "redis" {
  name                = format("%s-rbc-redis-pe", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.default.id
  private_service_connection {
    name                           = "redis-psc"
    private_connection_resource_id = azurerm_redis_cache.main.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = format("%s-rbc-law", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = format("%s-rbc-env", var.partner)
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
}

resource "azurerm_container_app" "main" {
  name                         = format("%s-rbc-app", var.partner)
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  tags                         = var.tags
  revision_mode                = "Single"

  template {
    container {
      name    = "rbc-api"
      image   = "blindchargingapi.azurecr.io/blind-charging-api:latest"
      cpu     = 1.0
      memory  = "2Gi"
      command = ["uvicorn", "app.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--app-dir", "/code/"]
      liveness_probe {
        host             = "localhost"
        path             = "/api/v1/health"
        port             = 8000
        transport        = "HTTP"
        initial_delay    = 5
        interval_seconds = 15
      }
    }

    container {
      name    = "rbc-worker"
      image   = "blindchargingapi.azurecr.io/blind-charging-api:latest"
      cpu     = 1.0
      memory  = "2Gi"
      command = ["python", "-m", "app.server", "worker", "--liveness-host", "0.0.0.0", "--liveness-port", "8001"]
      liveness_probe {
        host             = "localhost"
        path             = "/health"
        port             = 8001
        transport        = "HTTP"
        initial_delay    = 5
        interval_seconds = 15
      }
    }
  }
}
