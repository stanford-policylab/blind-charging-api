
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
    name                  = "rbc-wl"
    workload_profile_type = "D4"
    minimum_count         = 1
    maximum_count         = 2
  }
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

    min_replicas = 1

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
