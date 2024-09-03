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
