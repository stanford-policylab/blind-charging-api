locals {
  app_gateway_name                    = format("%s-rbc-app-gw", var.partner)
  frontend_ip_config_name             = format("%s-rbc-app-gw-feip", var.partner)
  frontend_https_port_name            = format("%s-rbc-app-gw-feport-https", var.partner)
  frontend_http_port_name             = format("%s-rbc-app-gw-feport-http", var.partner)
  https_listener_name                 = format("%s-rbc-app-gw-listener", var.partner)
  http_listener_name                  = format("%s-rbc-app-gw-listener-http", var.partner)
  http_to_https_redirect_name         = format("%s-rbc-app-gw-redirect", var.partner)
  backend_address_pool_name           = format("%s-rbc-app-gw-be-pool", var.partner)
  backend_http_settings_name          = format("%s-rbc-app-gw-be-settings", var.partner)
  ssl_cert_name                       = format("%s-rbc-app-gw-cert", var.partner)
  private_link_configuration_name     = format("%s-rbc-app-gw-plc", var.partner)
  probe_name                          = format("%s-rbc-app-gw-probe", var.partner)
  research_backend_address_pool_name  = format("%s-rbc-app-gw-be-pool-research", var.partner)
  research_backend_http_settings_name = format("%s-rbc-app-gw-be-settings-research", var.partner)
  research_probe_name                 = format("%s-rbc-app-gw-probe-research", var.partner)
  research_rewrite_rule_set_name      = format("%s-rbc-app-gw-rewrite-rule-set-research", var.partner)
  url_path_map_name                   = format("%s-rbc-app-gw-url-path-map", var.partner)
}


### SHADY CERTIFICATE THINGS ###
# NOTE(jnu) -- This self-signed certificate is ONLY useful for bootstrapping
# a quick environment for testing. In production, exposed apps need to use
# a real certificate issued for a real custom domain.
resource "tls_private_key" "app_gateway" {
  count     = var.expose_app ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "app_gateway" {
  count           = var.expose_app ? 1 : 0
  private_key_pem = tls_private_key.app_gateway[0].private_key_pem
  subject {
    common_name  = local.app_fqdn
    organization = format("%s Race Blind Charging", var.partner)
  }
  validity_period_hours = 8760
  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

resource "pkcs12_from_pem" "app_gateway" {
  count           = var.expose_app ? 1 : 0
  password        = var.ssl_cert_password
  private_key_pem = tls_private_key.app_gateway[0].private_key_pem
  cert_pem        = tls_self_signed_cert.app_gateway[0].cert_pem
}

### END SHADY CERTIFICATE THINGS ###

resource "azurerm_application_gateway" "public" {
  count               = var.expose_app ? 1 : 0
  name                = local.app_gateway_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku {
    name     = var.waf ? "WAF_v2" : "Standard_v2"
    tier     = var.waf ? "WAF_v2" : "Standard_v2"
    capacity = 2
  }

  // Set up general networking stuff for the gateway

  waf_configuration {
    enabled            = var.waf
    firewall_mode      = "Prevention"
    rule_set_type      = "OWASP"
    rule_set_version   = "3.2"
    request_body_check = false
  }

  gateway_ip_configuration {
    name      = format("%s-rbc-app-gw-ip", var.partner)
    subnet_id = azurerm_subnet.gateway.id
  }

  private_link_configuration {
    name = local.private_link_configuration_name
    ip_configuration {
      name                          = format("%s-rbc-app-gw-plcipcfg", var.partner)
      subnet_id                     = azurerm_subnet.gateway-pl.id
      private_ip_address_allocation = "Dynamic"
      primary                       = true
    }
  }

  frontend_ip_configuration {
    name                            = local.frontend_ip_config_name
    public_ip_address_id            = azurerm_public_ip.gateway[0].id
    private_link_configuration_name = local.private_link_configuration_name
  }

  frontend_ip_configuration {
    name                          = format("%s-rbc-app-gw-feip-priv", var.partner)
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.0.6.66"
    subnet_id                     = azurerm_subnet.gateway.id
  }

  // Set up an http -> https redirect

  frontend_port {
    name = local.frontend_http_port_name
    port = 80
  }

  http_listener {
    name                           = local.http_listener_name
    frontend_ip_configuration_name = local.frontend_ip_config_name
    frontend_port_name             = local.frontend_http_port_name
    protocol                       = "Http"
  }

  request_routing_rule {
    priority                    = 1
    name                        = format("%s-rbc-app-gw-rr-http-upgrade", var.partner)
    rule_type                   = "Basic"
    redirect_configuration_name = local.http_to_https_redirect_name
    http_listener_name          = local.http_listener_name
  }

  redirect_configuration {
    name                 = local.http_to_https_redirect_name
    redirect_type        = "Permanent"
    target_listener_name = local.https_listener_name
    include_path         = true
    include_query_string = true
  }

  // Set up the https listener

  frontend_port {
    name = local.frontend_https_port_name
    port = 443
  }

  ssl_certificate {
    name     = local.ssl_cert_name
    data     = pkcs12_from_pem.app_gateway[0].result
    password = var.ssl_cert_password
  }

  http_listener {
    name                           = local.https_listener_name
    frontend_ip_configuration_name = local.frontend_ip_config_name
    frontend_port_name             = local.frontend_https_port_name
    protocol                       = "Https"
    ssl_certificate_name           = local.ssl_cert_name
  }

  request_routing_rule {
    priority           = 2
    name               = format("%s-rbc-app-gw-rr", var.partner)
    rule_type          = "PathBasedRouting"
    url_path_map_name  = local.url_path_map_name
    http_listener_name = local.https_listener_name
  }

  url_path_map {
    name                               = local.url_path_map_name
    default_backend_address_pool_name  = local.backend_address_pool_name
    default_backend_http_settings_name = local.backend_http_settings_name

    path_rule {
      name                       = "api"
      paths                      = ["/api*"]
      backend_address_pool_name  = local.backend_address_pool_name
      backend_http_settings_name = local.backend_http_settings_name
    }

    dynamic "path_rule" {
      for_each = var.expose_research_env ? [1] : []
      content {
        name                       = "research"
        paths                      = ["/research*"]
        backend_address_pool_name  = local.research_backend_address_pool_name
        backend_http_settings_name = local.research_backend_http_settings_name
        rewrite_rule_set_name      = local.research_rewrite_rule_set_name
      }
    }
  }

  // Set up the app backend

  backend_address_pool {
    name  = local.backend_address_pool_name
    fqdns = [local.app_fqdn]
  }

  backend_http_settings {
    name                                = local.backend_http_settings_name
    probe_name                          = local.probe_name
    cookie_based_affinity               = "Disabled"
    port                                = 443
    protocol                            = "Https"
    request_timeout                     = 20
    pick_host_name_from_backend_address = true
  }

  probe {
    name                                      = local.probe_name
    protocol                                  = "Https"
    pick_host_name_from_backend_http_settings = true
    path                                      = "/api/v1/health"
    interval                                  = 30
    timeout                                   = 30
    unhealthy_threshold                       = 3
  }

  // Set up the research environment routing if requested

  dynamic "backend_http_settings" {
    for_each = var.expose_research_env ? [1] : []
    content {
      name                                = local.research_backend_http_settings_name
      probe_name                          = local.research_probe_name
      cookie_based_affinity               = "Disabled"
      port                                = 443
      protocol                            = "Https"
      request_timeout                     = 20
      pick_host_name_from_backend_address = true
    }
  }

  dynamic "backend_address_pool" {
    for_each = var.expose_research_env ? [1] : []
    content {
      name  = local.research_backend_address_pool_name
      fqdns = [local.research_app_fqdn]
    }
  }

  dynamic "probe" {
    for_each = var.expose_research_env ? [1] : []
    content {
      name                                      = local.research_probe_name
      protocol                                  = "Https"
      pick_host_name_from_backend_http_settings = true
      path                                      = "/unsupported_browser.htm"
      interval                                  = 30
      timeout                                   = 30
      unhealthy_threshold                       = 3
    }
  }

  dynamic "rewrite_rule_set" {
    for_each = var.expose_research_env ? [1] : []
    content {
      name = local.research_rewrite_rule_set_name

      rewrite_rule {
        name          = "research"
        rule_sequence = 1
        condition {
          ignore_case = false
          pattern     = "/research(.*)"
          negate      = false
          variable    = "var_request_uri"
        }
        url {
          path = "{var_request_uri_1}"
        }
      }
    }
  }
}
