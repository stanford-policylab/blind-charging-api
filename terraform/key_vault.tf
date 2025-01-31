
resource "azurerm_user_assigned_identity" "admin" {
  name                = local.user_assigned_admin_identity_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}


resource "azurerm_key_vault" "default" {
  name                        = local.key_vault_name
  resource_group_name         = azurerm_resource_group.main.name
  location                    = azurerm_resource_group.main.location
  enabled_for_disk_encryption = true
  soft_delete_retention_days  = 7
  purge_protection_enabled    = true
  # NOTE(jnu) - premium is required for HSM keys
  sku_name  = "premium"
  tenant_id = azurerm_user_assigned_identity.admin.tenant_id

  access_policy {
    tenant_id          = data.azurerm_client_config.current.tenant_id
    object_id          = data.azurerm_client_config.current.object_id
    secret_permissions = ["Get"]
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
    tenant_id       = azurerm_user_assigned_identity.admin.tenant_id
    object_id       = azurerm_user_assigned_identity.admin.principal_id
    key_permissions = ["Get", "WrapKey", "UnwrapKey"]

  }
}

resource "azurerm_key_vault_key" "encryption" {
  name         = "encryption-key"
  key_vault_id = azurerm_key_vault.default.id
  key_type     = "RSA-HSM"
  key_size     = 2048
  key_opts     = ["unwrapKey", "wrapKey", "decrypt", "encrypt", "sign", "verify"]
}
