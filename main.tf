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

variable "subscription_id" {
  type = string
}

variable "partner" {
  type = string
}

variable "db_user" {
  type    = string
  default = "bcadmin"
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

variable "registry_password" {
  type      = string
  sensitive = true
}

variable "tags" {
  type = map(string)
  default = {
    "environment" = "production"
    "app"         = "raceblind"
  }
}

# NOTE: this should *always* be true in production
# Only disable this when the Azure subscription has not been approved to disable filters,
# and we want to deploy the infrastructure anyway. (It must then be enabled later, or the
# race-blind API will not work as expected.)
variable "disable_content_filter" {
  type    = bool
  default = true
}

provider "azurerm" {
  subscription_id = var.subscription_id
  environment     = var.azure_env

  features {
  }
}

data "azurerm_client_config" "current" {}

provider "azapi" {
  tenant_id       = data.azurerm_client_config.current.tenant_id
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
  name                          = format("%s-rbc-sql", var.partner)
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "12.0"
  administrator_login           = var.db_user
  administrator_login_password  = var.db_password
  tags                          = var.tags
  public_network_access_enabled = false
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

resource "azurerm_mssql_firewall_rule" "app" {
  name             = format("%s-rbc-db-fw", var.partner)
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
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

resource "azurerm_cognitive_account" "fr" {
  name                  = format("%s-rbc-cs-fr", var.partner)
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  sku_name              = "S0"
  kind                  = "FormRecognizer"
  tags                  = var.tags
  custom_subdomain_name = format("%s-rbc-cs-fr", var.partner)
}

resource "azurerm_cognitive_account" "openai" {
  name                  = format("%s-rbc-cs-oai", var.partner)
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  sku_name              = "S0"
  kind                  = "OpenAI"
  tags                  = var.tags
  custom_subdomain_name = format("%s-rbc-cs-oai", var.partner)
}

# TODO(jnu): azurerm does not support the content filter resource yet.check "name"
# See https://github.com/hashicorp/terraform-provider-azurerm/issues/22822
resource "azapi_resource" "no_content_filter" {
  count                     = var.disable_content_filter ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/raiPolicies@2023-10-01-preview"
  name                      = "NoFilter"
  parent_id                 = azurerm_cognitive_account.openai.id
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
  depends_on = [azurerm_cognitive_account.openai]
}

resource "azurerm_cognitive_deployment" "llm" {
  name                 = format("%s-rbc-oai-llm", var.partner)
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-05-13"
  }
  sku {
    name     = "Standard"
    capacity = 80
  }
  rai_policy_name        = var.disable_content_filter ? azapi_resource.no_content_filter[0].name : "Default"
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

resource "azurerm_private_endpoint" "openai" {
  name                = format("%s-rbc-cs-oai-pe", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.default.id
  private_service_connection {
    name                           = "cs-oai-psc"
    private_connection_resource_id = azurerm_cognitive_account.openai.id
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

resource "azurerm_private_endpoint" "fr" {
  name                = format("%s-rbc-cs-fr-pe", var.partner)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.default.id
  private_service_connection {
    name                           = "cs-fr-psc"
    private_connection_resource_id = azurerm_cognitive_account.fr.id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_dns_zone" "main" {
  name                = format("%s.rbc.cpl.azure.com", var.partner)
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "main" {
  name                  = format("%s-rbc-dns-link", var.partner)
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.main.name
  virtual_network_id    = azurerm_virtual_network.main.id
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

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 1
    maximum_count         = 2
  }
}

locals {
  app_config_toml = <<EOF
debug = true

[queue]

[queue.store]
engine = "redis"
host = "${azurerm_private_endpoint.redis.custom_dns_configs.0.fqdn}"
ssl = true
port = 6380
password = "${azurerm_redis_cache.main.primary_access_key}"
database = 0

[queue.broker]
engine = "redis"
ssl = true
host = "${azurerm_private_endpoint.redis.custom_dns_configs.0.fqdn}"
port = 6380
password = "${azurerm_redis_cache.main.primary_access_key}"
database = 1

[experiments]
enabled = true
automigrate = false

[experiments.store]
engine = "mssql"
user = "${var.db_user}"
password = "${var.db_password}"
host = "${azurerm_private_endpoint.mssql.custom_dns_configs.0.fqdn}"
database = "${azurerm_mssql_database.main.name}"

[processor]
# Configure the processing pipeline.

[[processor.pipe]]
# 1) Extract / OCR with Azure DI
engine = "extract:azuredi"
endpoint = "${azurerm_cognitive_account.fr.endpoint}"
api_key = "${azurerm_cognitive_account.fr.primary_access_key}"
extract_labeled_text = false

[[processor.pipe]]
# 2) Parse textual output into coherent narrative with OpenAI
engine = "parse:openai"
[processor.pipe.client]
azure_endpoint = "${azurerm_cognitive_account.openai.endpoint}"
api_key = "${azurerm_cognitive_account.openai.primary_access_key}"
api_version = "2024-06-01"

[processor.pipe.generator]
method = "chat"
model = "${azurerm_cognitive_deployment.llm.model[0].name}"
system = { prompt = """\
I am providing you with a list of paragraphs extracted from a \
police report via Azure Document Intelligence.

Please extract any and all paragraphs in this output that were \
derived from a police narrative. A police narrative is a detailed \
account of events that occurred during a police incident. It typically \
includes information such as the date, time, location, and description \
of the incident, as well as the actions taken by the police officers \
involved.

You should return back ONLY these paragraphs. Do not return anything \
else.

If you are unable to identify any police narratives in the output, \
please return an empty string.""" }

[[processor.pipe]]
# 3) Redact racial information with OpenAI
engine = "redact:openai"
delimiters = ["[", "]"]
[processor.pipe.client]
azure_endpoint = "${azurerm_cognitive_account.openai.endpoint}"
api_key = "${azurerm_cognitive_account.openai.primary_access_key}"
api_version = "2024-06-01"

[processor.pipe.generator]
method = "chat"
model = "${azurerm_cognitive_deployment.llm.model[0].name}"
system = { prompt = """\
Your job is to redact all race-related information in the provided \
text. Race-related information is any word from the following strict \
categories:
- Explicit mentions of race or ethnicity
- People's names
- Physical descriptions: Hair color, eye color, or skin color ONLY
- Location information: Addresses, neighborhood names, commercial \
establishment names, or major landmarks

Do NOT redact any other types of information, e.g., do not redact \
dates, objects, or other types of words not listed here.

Replace any person's name with an abbreviation indicating their role \
in the incident. For example, for the first mentioned victim, use
"[Victim 1]". Similarly, for the second mentioned victim, use \
"[Victim 2]". Be as specific as possible about their role (e.g., \
"Officer Smith and Sergeant Doe" should become "[Officer 1] and \
[Sergeant 1]"). If a person's role in the incident is unclear, \
use a generic “[Person X]” (with X replaced by the appropriate \
number).

If "John Doe" appears in the list of individuals, and then "Johnny \
D." appears in the narrative, use context to decide if "Johnny D." \
should be redacted with the same replacement as "John Doe." \
Similarly, if "Safeway" appears in the list of locations with \
abbreviation [Store 1], "Safeway Deli" should be redacted as \
"[Store 1] Deli".""" }
EOF
}

resource "azurerm_container_app" "main" {
  name                         = format("%s-rbc-app", var.partner)
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  tags                         = var.tags
  revision_mode                = "Single"

  timeouts {
    create = "30m"
    update = "30m"
  }

  identity {
    type = "SystemAssigned"
  }

  secret {
    name  = "registry-password"
    value = var.registry_password
  }

  secret {
    name  = "app-config"
    value = local.app_config_toml
  }

  registry {
    server               = "blindchargingapi.azurecr.io"
    username             = var.partner
    password_secret_name = "registry-password"
  }

  template {

    volume {
      name         = "secrets"
      storage_type = "Secret"
    }

    init_container {
      name    = "rbc-init-ensure-db"
      image   = "blindchargingapi.azurecr.io/blind-charging-api:latest"
      cpu     = 1.0
      memory  = "2Gi"
      command = ["python"]
      args    = ["-m", "app.server", "create-db"]
      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }
      env {
        name  = "CONFIG_PATH"
        value = "/secrets/app-config"
      }
    }

    container {
      name    = "rbc-api"
      image   = "blindchargingapi.azurecr.io/blind-charging-api:latest"
      cpu     = 1.0
      memory  = "2Gi"
      command = ["uvicorn"]
      args    = ["app.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--app-dir", "/code/"]
      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }
      env {
        name  = "CONFIG_PATH"
        value = "/secrets/app-config"
      }
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
      command = ["python"]
      args    = ["-m", "app.server", "worker", "--liveness-host", "0.0.0.0", "--liveness-port", "8001"]
      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }
      env {
        name  = "CONFIG_PATH"
        value = "/secrets/app-config"
      }
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
