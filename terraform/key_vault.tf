
resource "azurerm_user_assigned_identity" "admin" {
  name                = local.user_assigned_admin_identity_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_user_assigned_identity" "app" {
  name                = local.user_assigned_app_identity_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}


resource "azurerm_key_vault" "main" {
  name                            = local.key_vault_name
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  enabled_for_disk_encryption     = true
  enabled_for_template_deployment = true
  enable_rbac_authorization       = true
  soft_delete_retention_days      = 7
  purge_protection_enabled        = true
  public_network_access_enabled   = false
  # NOTE(jnu) - premium is required for HSM keys
  sku_name  = "premium"
  tenant_id = azurerm_user_assigned_identity.admin.tenant_id

  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = data.azurerm_client_config.current.object_id
    secret_permissions = ["Get", "Set", "Delete", "Purge", "Recover", "List"]
    key_permissions = [
      "Get",
      "Create",
      "Delete",
      "List",
      "Restore",
      "Recover",
      "UnwrapKey",
      "WrapKey",
      "Purge",
      "Encrypt",
      "Decrypt",
      "Sign",
      "Verify",
      "GetRotationPolicy",
      "SetRotationPolicy"
    ]
  }

  access_policy {
    tenant_id          = azurerm_user_assigned_identity.admin.tenant_id
    object_id          = azurerm_user_assigned_identity.admin.principal_id
    key_permissions    = ["Get", "WrapKey", "UnwrapKey"]
    secret_permissions = ["Get", "List"]
  }

  access_policy {
    tenant_id          = azurerm_user_assigned_identity.app.tenant_id
    object_id          = azurerm_user_assigned_identity.app.principal_id
    secret_permissions = ["Get"]
  }
}

resource "azurerm_key_vault_key" "encryption" {
  name         = "encryption-key"
  key_vault_id = azurerm_key_vault.main.id
  key_type     = "RSA-HSM"
  key_size     = 2048
  key_opts     = ["unwrapKey", "wrapKey", "decrypt", "encrypt", "sign", "verify"]
}

resource "azurerm_private_endpoint" "kv" {
  name                = local.key_vault_private_endpoint_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.kv.id
  tags                = var.tags
  private_service_connection {
    name                           = "cs-kv-psc"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }
  private_dns_zone_group {
    name                 = "pdz-cs-kv"
    private_dns_zone_ids = [azurerm_private_dns_zone.kv.id]
  }
}
