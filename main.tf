terraform {
    required_providers {
        azurerm = {
            source = "hashicorp/azurerm"
            version = "~> 4.0.1"
        }
        azapi = {
            source = "azure/azapi"
            version = "~> 1.15.0"
        }
    }

    required_version = ">= 1.5.7"
}

variable "partner" {
    type = string
}

variable "db_password" {
    type = string
}

variable "vm_password" {
    type = string
}

variable "ssh_pub_key" {
    type = string
    default = "~/.ssh/id_rsa.pub"
}

variable "tags" {
    type = map(string)
    default = {
      "environment" = "production"
      "app" = "raceblind"
    }
}

provider "azurerm" {
    features {}
}

provider "azapi" {
}

resource "azurerm_resource_group" "main" {
    name     = "RaceBlindCharging"
    location = "usgovvirginia"
    tags = var.tags
}

resource "azurerm_redis_cache" "main" {
    name                = format("%s-rbc-redis", var.partner)
    resource_group_name = azurerm_resource_group.main.name
    location            = azurerm_resource_group.main.location
    capacity            = 3
    family              = "C"
    sku_name            = "Standard"
    non_ssl_port_enabled = false
    tags = var.tags
}

resource "azurerm_mssql_server" "main" {
    name                         = format("%s-rbc-sql", var.partner)
    resource_group_name          = azurerm_resource_group.main.name
    location                     = azurerm_resource_group.main.location
    version                      = "12.0"
    administrator_login          = "sa"
    administrator_login_password = var.db_password
    tags = var.tags
}

resource "azurerm_mssql_database" "main" {
    name                = format("%s-rbc-db", var.partner)
    server_id           = azurerm_mssql_server.main.id
    collation           = "SQL_Latin1_General_CP1_CI_AS"
    max_size_gb         = 4
    sku_name = "S0"
    zone_redundant = false
    tags = var.tags
    enclave_type = "VBS"
    lifecycle {
        prevent_destroy = true
    }
}

resource "azurerm_virtual_network" "main" {
    name                = format("%s-rbc-vnet", var.partner)
    resource_group_name = azurerm_resource_group.main.name
    location            = azurerm_resource_group.main.location
    address_space       = ["10.0.0.6/16"]

    subnet {
        name              = "default"
        address_prefixes  = ["10.0.0.0/24"]
        service_endpoints = ["Microsoft.CognitiveServices"]
    }
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
    type = "Microsoft.CognitiveServices/accounts/raiPolicies@2023-10-01-preview"
    name = "NoFilter"
    parent_id = azurerm_cognitive_account.main.id
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
    name                = format("%s-rbc-cognitive-deployment", var.partner)
    cognitive_account_id = azurerm_cognitive_account.main.id
    model {
        format = "OpenAI"
        name = "gpt-4o"
        version = "2024-05-13"
    }
    sku {
        name = "Standard"
        tier = "Standard"
        capacity = 80
    }
    rai_policy_name = azapi_resource.no_content_filter.name
    version_upgrade_option = "NoAutoUpgrade"
}

resource "azurerm_private_endpoint" "mssql" {
    name                = format("%s-rbc-mssql-pe", var.partner)
    resource_group_name = azurerm_resource_group.main.name
    location            = azurerm_resource_group.main.location
    subnet_id           = azurerm_virtual_network.main.subnet[0].id
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
    subnet_id           = azurerm_virtual_network.main.subnet[0].id
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
    subnet_id           = azurerm_virtual_network.main.subnet[0].id
    private_service_connection {
        name                           = "redis-psc"
        private_connection_resource_id = azurerm_redis_cache.main.id
        subresource_names              = ["redisCache"]
        is_manual_connection           = false
    }
}

resource "azurerm_network_interface" "vm" {
    name                = format("%s-rbc-vm-nic", var.partner)
    resource_group_name = azurerm_resource_group.main.name
    location            = azurerm_resource_group.main.location

    ip_configuration {
        name                          = "internal"
        subnet_id                     = azurerm_virtual_network.main.subnet[0].id
        private_ip_address_allocation = "Static"
        private_ip_address            = "10.0.0.10"
    }
}

resource "azurerm_linux_virtual_machine" "main" {
    name                = format("%s-rbc-vm", var.partner)
    resource_group_name = azurerm_resource_group.main.name
    location            = azurerm_resource_group.main.location
    size                = "Standard_B2s"
    admin_username      = "admin"
    admin_ssh_key {
        username   = "admin"
        public_key = file(var.ssh_pub_key)
    }
    network_interface_ids = [azurerm_network_interface.vm.id]
    os_disk {
        caching              = "ReadWrite"
        storage_account_type = "Standard_LRS"
    }
    source_image_reference {
        publisher = "Canonical"
        offer     = "0001-com-ubuntu-server-jammy"
        sku       = "22.04-LTS"
        version   = "latest"
    }
    tags = var.tags
}
