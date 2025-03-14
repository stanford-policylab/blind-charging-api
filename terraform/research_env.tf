locals {
  research_app_fqdn = format("%s.%s", local.research_app_name, azurerm_container_app_environment.main.default_domain)
}

resource "azurerm_storage_account" "research" {
  count                    = var.enable_research_env ? 1 : 0
  name                     = local.research_storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = var.tags
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.admin.id]
  }
  customer_managed_key {
    key_vault_key_id          = azurerm_key_vault_key.encryption.versionless_id
    user_assigned_identity_id = azurerm_user_assigned_identity.admin.id
  }
}

resource "azurerm_storage_share" "research" {
  count              = var.enable_research_env ? 1 : 0
  name               = var.research_storage_share_name
  storage_account_id = azurerm_storage_account.research[0].id
  quota              = 10 # Gigabytes
}

resource "azurerm_container_app_environment_storage" "research" {
  count                        = var.enable_research_env ? 1 : 0
  name                         = format("%s-data-caes", local.research_app_name)
  container_app_environment_id = azurerm_container_app_environment.main.id
  account_name                 = azurerm_storage_account.research[0].name
  share_name                   = azurerm_storage_share.research[0].name
  access_key                   = azurerm_storage_account.research[0].primary_access_key
  access_mode                  = "ReadWrite"
}

resource "azurerm_key_vault_secret" "research_config" {
  count        = var.enable_research_env ? 1 : 0
  name         = "research-config"
  key_vault_id = azurerm_key_vault.main.id
  value        = local.research_env_toml
}

resource "azurerm_key_vault_secret" "research_password" {
  count        = var.enable_research_env ? 1 : 0
  name         = "research-password"
  key_vault_id = azurerm_key_vault.main.id
  value        = var.research_password
}

resource "azurerm_container_app" "research" {
  count                        = var.enable_research_env ? 1 : 0
  name                         = local.research_app_name
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  tags                         = var.tags
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  timeouts {
    create = "30m"
    update = "30m"
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.admin.id]
  }

  secret {
    name                = "researchpassword"
    identity            = azurerm_user_assigned_identity.admin.id
    key_vault_secret_id = azurerm_key_vault_secret.research_password[0].versionless_id
  }

  secret {
    name                = "registrypassword"
    identity            = azurerm_user_assigned_identity.admin.id
    key_vault_secret_id = azurerm_key_vault_secret.registry_password.versionless_id
  }

  secret {
    name                = "config"
    identity            = azurerm_user_assigned_identity.admin.id
    key_vault_secret_id = azurerm_key_vault_secret.research_config[0].versionless_id
  }

  registry {
    server               = var.research_image_registry
    username             = var.partner
    password_secret_name = "registrypassword"
  }

  ingress {
    allow_insecure_connections = false
    target_port                = 8787
    external_enabled           = true
    transport                  = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {

    min_replicas = 1
    max_replicas = 1

    volume {
      name         = "secrets"
      storage_type = "Secret"
    }

    volume {
      name         = "data"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.research[0].name
    }

    container {
      name   = "rbc-research"
      image  = local.research_image_tag
      cpu    = 2.0
      memory = "4Gi"

      env {
        name        = "PASSWORD"
        secret_name = "researchpassword"
      }

      volume_mounts {
        name = "data"
        path = "/data"
      }

      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }

      liveness_probe {
        host             = "127.0.0.1"
        path             = "/unsupported_browser.htm"
        port             = 8787
        transport        = "HTTP"
        initial_delay    = 5
        interval_seconds = 15
      }
    }
  }
}

// azurerm doesn't support "mount options" yet. "noperm" is required
// for the SMB share to work properly.
// https://github.com/hashicorp/terraform-provider-azurerm/issues/26131
//
// "noperm" is not actually valid in Azure, so we use `uid` and `gid`
// instead and this will give `rstudio` user the permission to do most
// things in this directory (unless they actually need to `chmod` or `chown`).
//
// Separately, azapi_update_resource only supports PUT, which hits an
// error since it will try to merge the config with secrets (which it can't
// find values for due to security reasons). azapi_resource_action is used
// instead to send a PATCH request.
// https://github.com/Azure/terraform-provider-azapi/issues/542
resource "azapi_resource_action" "fix_smb_mount_options" {

  count       = var.enable_research_env ? 1 : 0
  resource_id = azurerm_container_app.research[0].id
  depends_on  = [azurerm_container_app.research[0]]
  type        = "Microsoft.App/containerApps@2024-03-01"
  method      = "PATCH"
  body = {
    properties = {
      template = {
        volumes = [
          {
            name        = "secrets"
            storageType = "Secret"
          },
          {
            name         = "data"
            storageType  = "AzureFile"
            storageName  = azurerm_container_app_environment_storage.research[0].name
            mountOptions = "dir_mode=0777,file_mode=0777,uid=1000,gid=1000,nobrl,mfsymlinks,cache=none"
          }
        ]
      }
    }
  }
}
