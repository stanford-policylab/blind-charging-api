locals {
  # The self-signed certificate should be the default option if the app is exposed to the private network.
  use_self_signed_cert = var.expose_app_to_private_network || (var.ssl_cert == "self_signed" && var.expose_app_to_public_internet)
  # LetsEncrypt can't work for internal certificates.
  use_lets_encrypt_cert = !var.expose_app_to_private_network && var.ssl_cert == "acme" && var.expose_app_to_public_internet
}

### Self-signed certificate ###
# This self-signed certificate is ONLY useful for bootstrapping
# a quick environment for testing. In production, exposed apps need to use
# a real certificate issued for a real custom domain.
resource "tls_private_key" "app_gateway" {
  count     = local.use_self_signed_cert ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "app_gateway" {
  count           = local.use_self_signed_cert ? 1 : 0
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
  count           = local.use_self_signed_cert ? 1 : 0
  password        = var.ssl_cert_password
  private_key_pem = tls_private_key.app_gateway[0].private_key_pem
  cert_pem        = tls_self_signed_cert.app_gateway[0].cert_pem
}

### Let's Encrypt certificate ###
# This certificate is useful for production environments.
#
# By default, you need to set the TXT record in your DNS provider manually.
# See `challenge.log` when running the script to get the value to set.
# You can also configure a DNS provider that supports automatic propagation;
# see the `ssl_dns_provider` and `ssl_dns_provider_config` variables.
resource "acme_registration" "app_gateway" {
  count = local.use_lets_encrypt_cert ? 1 : 0

  email_address = var.ssl_cert_email
}

resource "acme_certificate" "app_gateway" {
  count = local.use_lets_encrypt_cert ? 1 : 0

  certificate_p12_password = var.ssl_cert_password
  account_key_pem          = acme_registration.app_gateway[0].account_key_pem
  common_name              = var.host

  dns_challenge {
    provider = var.ssl_dns_provider == "manual" ? "exec" : var.ssl_dns_provider
    config = var.ssl_dns_provider == "manual" ? {
      EXEC_PATH                = "${path.module}/backend/cert.sh"
      EXEC_PROPAGATION_TIMEOUT = "900" # 15 minutes
    } : var.ssl_dns_provider_config
  }
}
