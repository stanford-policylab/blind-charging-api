resource "azurerm_container_app_environment" "main" {
  name                               = local.container_app_env_name
  resource_group_name                = azurerm_resource_group.main.name
  location                           = azurerm_resource_group.main.location
  logs_destination                   = "azure-monitor"
  tags                               = var.tags
  infrastructure_resource_group_name = var.app_infra_resource_group_name
  infrastructure_subnet_id           = azurerm_subnet.app.id
  internal_load_balancer_enabled     = true
  mutual_tls_enabled                 = true

  workload_profile {
    # TODO(jnu): Dedicated workload profile does not seem to be supported,
    # but will be needed for production.
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 1
    maximum_count         = 2
  }
}

resource "azurerm_monitor_diagnostic_setting" "container_app" {
  name                       = "container-app"
  target_resource_id         = azurerm_container_app_environment.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  # TODO(jnu): appears to be an issue in some environments setting this up.
  # Disabling for now pending investigation:
  # https://github.com/Azure/terraform-azurerm-avm-res-network-networksecuritygroup/issues/39
  # metric {
  #  category = "AllMetrics"
  #  enabled  = true
  # }
}

locals {
  app_fqdn = format("%s.%s", local.container_app_name, azurerm_container_app_environment.main.default_domain)
}

resource "azurerm_key_vault_secret" "app_config" {
  name         = "app-config"
  key_vault_id = azurerm_key_vault.main.id
  value        = local.app_config_toml
}

resource "azurerm_key_vault_secret" "registry_password" {
  name         = "registry-password"
  key_vault_id = azurerm_key_vault.main.id
  value        = var.registry_password
}

resource "azurerm_container_app" "main" {
  name                         = local.container_app_name
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
    name                = "registry-password"
    identity            = azurerm_user_assigned_identity.admin.id
    key_vault_secret_id = azurerm_key_vault_secret.registry_password.versionless_id
  }

  secret {
    name                = "app-config"
    identity            = azurerm_user_assigned_identity.admin.id
    key_vault_secret_id = azurerm_key_vault_secret.app_config.versionless_id
  }

  registry {
    server               = var.api_image_registry
    username             = var.partner
    password_secret_name = "registry-password"
  }

  ingress {
    allow_insecure_connections = false
    target_port                = 8000
    exposed_port               = null
    external_enabled           = true
    # We only support HTTPS transports.
    # To support `https`, we specify `http` here with insecure connections disallowed.
    transport = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {

    volume {
      name         = "secrets"
      storage_type = "Secret"
    }

    min_replicas = 1

    init_container {
      name   = "rbc-init-ensure-db"
      image  = local.api_image_tag
      cpu    = 1.0
      memory = "2Gi"
      args   = ["create-db"]
      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }
      env {
        name  = "CONFIG_PATH"
        value = "/secrets/app-config"
      }

      dynamic "env" {
        for_each = var.api_flags
        content {
          name  = env.key
          value = env.value
        }
      }
    }

    container {
      # Debugging container for when all else fails.
      name   = "rbc-debug"
      image  = local.api_image_tag
      cpu    = 1.0
      memory = "2Gi"

      command = ["/bin/bash"]
      args    = ["-c", "trap : TERM INT; sleep infinity & wait"]

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
      name   = "rbc-api"
      image  = local.api_image_tag
      cpu    = 1.0
      memory = "2Gi"
      args   = ["api", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }
      env {
        name  = "CONFIG_PATH"
        value = "/secrets/app-config"
      }

      dynamic "env" {
        for_each = var.api_flags
        content {
          name  = env.key
          value = env.value
        }
      }

      liveness_probe {
        host             = "127.0.0.1"
        path             = "/api/v1/health"
        port             = 8000
        transport        = "HTTP"
        initial_delay    = 5
        interval_seconds = 15
      }
    }

    container {
      name   = "rbc-worker"
      image  = local.api_image_tag
      cpu    = 2.0
      memory = "4Gi"
      args   = ["worker", "--liveness-host", "0.0.0.0", "--liveness-port", "8001"]
      volume_mounts {
        name = "secrets"
        path = "/secrets"
      }
      env {
        name  = "CONFIG_PATH"
        value = "/secrets/app-config"
      }

      dynamic "env" {
        for_each = var.api_flags
        content {
          name  = env.key
          value = env.value
        }
      }

      liveness_probe {
        host                    = "127.0.0.1"
        path                    = "/health"
        port                    = 8001
        transport               = "HTTP"
        initial_delay           = 10
        interval_seconds        = 15
        failure_count_threshold = 3
        timeout                 = 5
      }
      readiness_probe {
        host                    = "127.0.0.1"
        path                    = "/health"
        port                    = 8001
        transport               = "HTTP"
        failure_count_threshold = 2
        timeout                 = 5
        interval_seconds        = 30
      }
      startup_probe {
        host                    = "127.0.0.1"
        path                    = "/health"
        port                    = 8001
        transport               = "HTTP"
        failure_count_threshold = 6
        interval_seconds        = 5
        timeout                 = 5
      }
    }
  }
}
