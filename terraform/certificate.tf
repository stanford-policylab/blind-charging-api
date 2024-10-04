locals {
  use_self_signed_cert  = var.ssl_cert == "self_signed" && var.expose_app
  use_lets_encrypt_cert = var.ssl_cert == "acme" && var.expose_app
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
# Unfortunately, we can't fully support Let's Encrypt yet, since not all
# DNS backends are supported. This means there's some manual action that
# needs to be taken in order to set the TXT record for the domain.
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
    provider = "exec"
    config = {
      EXEC_PATH                = "${path.module}/backend/cert.sh"
      EXEC_PROPAGATION_TIMEOUT = "900" # 15 minutes
    }
  }
}