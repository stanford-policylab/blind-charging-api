variable "subscription_id" {
  type        = string
  description = "Azure subscription ID to deploy to. The subscription must be set up before running Terraform."
}

variable "debug" {
  type        = bool
  default     = false
  description = "Enable debug mode for the application."
}

variable "toy_mode" {
  type        = bool
  default     = false
  description = <<EOF
Enable demo mode for the application.

This will disable the expensive features like OpenAI and Azure Form Recognizer,
opting instead for fast and cheap (but low-quality) alternatives.
EOF
}

variable "partner" {
  type        = string
  description = "Name of the group deploying this infrastructure. This is used for naming resources."
}

variable "db_user" {
  type        = string
  default     = "bcadmin"
  description = "Admin username for the MSSQL database. See Azure documentation for disallowed values."
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Admin password for the MSSQL database. This can be any strong string and should be rotated periodically."
}

variable "location" {
  type        = string
  default     = "usgovvirginia"
  description = "Azure region to deploy to. Available options depend on the Azure environment."
}

variable "openai_location" {
  type        = string
  default     = null
  nullable    = true
  description = <<EOF
Azure region to deploy the OpenAI cognitive service to. Available options depend on the Azure environment.

By default, this is the same as the main location.
Some models are not available in all regions, so the default location can be overridden as needed.
EOF
}

variable "azure_env" {
  type        = string
  default     = "usgovernment"
  description = "Azure environment to deploy to. Normally this is GovCloud, but does not have to be."
}

variable "expose_app_to_public_internet" {
  type        = bool
  default     = false
  description = <<EOF
Configure gateway so that the app is reachable over the public internet.

This will create an Application Gateway with a public IP address that can
be reachable over the public internet. This should be used in combination
with a WAF and other security measures.
EOF
}

variable "expose_app_to_private_network" {
  type        = bool
  default     = true
  description = <<EOF
Configure gateway so that other Azure private networks can access the app.

This will create an Application Gateway with a private IP address
and configure private link so that a private endpoint can be created
in another vnet to access this app.
EOF
}

variable "waf" {
  type        = bool
  default     = true
  description = <<EOF
Enable the Web Application Firewall for the application gateway.

This should be enabled if `expose_app_to_public_internet` is true.
EOF
}

variable "peered_network_id" {
  type        = string
  nullable    = true
  default     = null
  description = "Make the app available to another virtual network via peering."
}

variable "ssl_cert_password" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Password for the SSL certificate."
}

variable "ssl_cert_email" {
  type        = string
  nullable    = true
  default     = null
  description = <<EOF
Email address to use for Let's Encrypt certificate registration.

This is only required if `ssl_cert` is set to 'acme'.
EOF
}

variable "ssl_p12_file" {
  type        = string
  nullable    = true
  default     = null
  description = <<EOF
Path to the P12 file to use for the SSL certificate.

This is only required if `ssl_cert` is set to 'file'.
EOF
}

variable "ssl_cert" {
  type    = string
  default = "none"
  validation {
    condition     = can(regex("^(none|self_signed|acme|file)$", var.ssl_cert))
    error_message = "ssl_cert must be one of 'none', 'self_signed', 'acme', or 'file'."
  }
}

variable "ssl_dns_provider" {
  type        = string
  default     = "manual"
  description = <<EOF
DNS provider to use for Let's Encrypt certificate registration.

By default we use manual provision, where you need to check `challenge.log` and update your DNS records manually
while running this script.

You generally need to provide additional environment variables to make the provider set here work.
EOF
}

variable "ssl_dns_provider_config" {
  type        = map(string)
  default     = {}
  description = <<EOF
Configuration for the DNS provider. See lego documentation for details for your provider.
EOF
}

variable "app_auth" {
  type    = string
  default = "none"
  validation {
    condition     = can(regex("^(none|preshared|client_credentials)$", var.app_auth))
    error_message = "app_auth must be one of 'none', 'preshared', or 'client_credentials'."
  }
  description = <<EOF
Authentication method for the application.

By default, no authentication is required.

`preshared` requires a shared secret to be set in `app_auth_secret`. It should be rotated periodically.

`client_credentials` requires a secret to be set in `app_auth_secret`. This is used for signing the token.
EOF
}

variable "app_auth_secret" {
  type        = string
  sensitive   = true
  nullable    = true
  default     = null
  description = "Secret used with client_credentials flow. (Required if app_auth is 'client_credentials'.)"
}

variable "registry_password" {
  type        = string
  sensitive   = true
  description = <<EOF
Password for authenticating with the container registry.

This value is typically issued from the Computational Policy Lab's Azure Container Registry;
the `blind-charging-api` image is only deployed there, and not in this Terraform configuration.
EOF
}

variable "api_image_registry" {
  type        = string
  default     = "blindchargingapi.azurecr.io"
  description = "The Docker image registry where the `api_image` is hosted."
}

variable "api_image" {
  type        = string
  default     = "blind-charging-api"
  description = "The base tag (without the version) of the Docker image used to run the API."
}

variable "api_image_version" {
  type        = string
  default     = "stable"
  description = <<EOF
The version of the Docker image used to run the API.

This version must exist in the repo specified in `var.api_image`.

**WARNING** If the tag is `stable` (the default!), the image version may upgrade
unexpectedly when the app containers restart. This is usually fine, but it's
recommended to lock the version and increment it manually in case a new image
contains incompatible changes.
EOF
}

variable "tags" {
  type = map(string)
  default = {
    "environment" = "production"
    "app"         = "raceblind"
  }
  description = "Tags to apply to all resources (for bookkeeping purposes)."
}

variable "tfstate_resource_group" {
  type        = string
  nullable    = true
  default     = null
  description = <<EOF
Resource group where the Terraform state is stored.

If not provided, the state will be stored locally.
EOF
}

variable "disable_content_filter" {
  type        = bool
  default     = true
  description = <<EOF
Disable the content filter for the OpenAI cognitive service.

This can only be set to false if the Azure subscription has been approved to disable filters.

This should *always* be true in production. Only set to false if you want to deploy while waiting \
for approval to disable filters. Once approved, re-deploy with this set to true.
EOF
}

variable "openai_llm_model" {
  type        = string
  default     = "gpt-4o"
  description = <<EOF
The OpenAI model to use for the LLM cognitive service.

This should be set to the model name in the OpenAI API, e.g., "gpt-4o" or "gpt-3.5-turbo".
EOF
}

variable "openai_llm_model_version" {
  type        = string
  default     = "2024-05-13"
  description = <<EOF
The version of the OpenAI model to use for the LLM cognitive service.
This should be set to the version in the OpenAI API, e.g., "2024-05-13".

Ensure that the model version is available on GovCloud, as the models differ between
GovCloud and Commercial cloud.
EOF
}

variable "openai_embedding_model" {
  type        = string
  default     = "text-embedding-3-large"
  description = <<EOF
The OpenAI model to use for the embedding cognitive service.

This should be set to the model name in the OpenAI API, e.g., "text-embedding-3-large".
EOF
}

variable "openai_embedding_model_version" {
  type        = string
  default     = "1"
  description = <<EOF
The version of the OpenAI model to use for the embedding cognitive service.

Typically these only have one version.
EOF
}

variable "openai_capacity" {
  type        = number
  default     = 80
  description = "In thousands of tokens per minute."
}

variable "openai_embedding_capacity" {
  type        = number
  default     = 120
  description = "In thousands of tokens per minute."
}

variable "host" {
  type        = string
  nullable    = true
  default     = null
  description = "The host domain where the application is deployed (on the public internet; not relevant if app is not exposed)."
}

variable "enable_research_env" {
  type        = bool
  default     = false
  description = "Configure the research analytics environment for the application."
}

variable "expose_research_env" {
  type        = bool
  default     = false
  description = "Expose the research environment to the public internet."
}

variable "research_password" {
  type        = string
  sensitive   = true
  default     = "ResearchAdminPassword##"
  description = "Password for the research environment."
}

variable "research_image_registry" {
  type        = string
  default     = "blindchargingapi.azurecr.io"
  description = "The Docker image registry where the `research_image` is hosted."
}

variable "research_image" {
  type        = string
  default     = "blind-charging-research"
  description = "The base tag (without the version) of the Docker image used to run the research server."
}

variable "research_image_version" {
  type        = string
  default     = "latest"
  description = <<EOF
The version of the Docker image used to run the research server.

This version must exist in the repo specified in `var.research_image`.

**WARNING** If the tag is `latest` (the default!), the image version may upgrade
unexpectedly when the app containers restart. This is usually fine, but it's
recommended to lock the version and increment it manually in case a new image
contains incompatible changes.
EOF
}

variable "dns_servers" {
  type        = list(string)
  default     = ["1.1.1.1"] # Cloudflare
  description = <<EOF
List of DNS servers to use for traffic filtering in the firewall.
EOF
}

variable "firewall_allowed_domains" {
  type        = list(string)
  default     = []
  description = <<EOF
List of domains to allow outbound traffic to through the firewall.

Note that we currently require access to our Azure Container Registry for the API image.
We will automatically apply rules that allow access to pull from this registry.

If you want to allow additional domains (e.g., blob storage), add them to this list.

This is required if you want us to write redacted documents to blob storage.
EOF
}

variable "allowed_ips" {
  type        = list(string)
  default     = ["0.0.0.0/0"]
  description = <<EOF
List of IP ranges to allow inbound traffic from.

By default, all traffic is allowed.

This is only relevant if the app is exposed to the public internet,
and the WAF is enabled.
EOF
}

variable "worker_threads" {
  type        = number
  default     = 10
  description = <<EOF
Number of concurrent workers to use in a process for processing requests.
EOF
}

variable "redis_sku_family" {
  type        = string
  default     = "C"
  description = <<EOF
Family of Azure Redis Cache SKU to use for deployment.

C is the default, which refers to the "Standard" SKU.

Use "E" to refer to the "Enterprise" SKU, and set the capacity sku accordingly.

For example, the following will correspond to the `Enterprise_E5` SKU:
  redis_sku_family = "E"
  redis_capacity_sku = 5

EOF
}

variable "redis_capacity_sku" {
  type        = number
  default     = 4
  description = <<EOF
SKU of Azure Redis Cache Standard to use for deployment.

We currently recommend C4 as a nice balance of memory and cost.

https://azure.microsoft.com/en-us/pricing/details/cache/
EOF
}

variable "redis_enterprise_vms" {
  type        = number
  default     = 2
  description = <<EOF
Number of VMs to run in the Redis Enterprise cluster.

This *only* applies to the Enterprise SKU and will be ignored in other circumstances.

This will ultimately determine how much RAM is available to the Redis cluster.

The default is 2, which for Enterprise_E5 will provide 4GB of RAM.
EOF
}

variable "queue_store_retention" {
  type        = number
  default     = 14400
  description = <<EOF
Number of seconds to retain data in the queue results store.

Default is 4 hours.
EOF
}

variable "api_flags" {
  type        = map(string)
  default     = {}
  description = <<EOF
Environment variables to pass to the API and worker containers.
EOF
}

variable "parse_chunks_max_iterations" {
  type        = number
  default     = 5
  description = <<EOF
Maximum number of iterations to run the parser.

This may be necessary to work around output token limits for LLM parsing.
EOF
}

variable "redact_chunks_max_iterations" {
  type        = number
  default     = 5
  description = <<EOF
Maximum number of iterations to run the redactor.

This may be necessary to work around output token limits for LLM redaction.
EOF
}


locals {
  is_gov_cloud       = var.azure_env == "usgovernment"
  description        = "Whether this configuration uses Azure Government Cloud."
  api_image_tag      = format("%s/%s:%s", var.api_image_registry, var.api_image, var.api_image_version)
  research_image_tag = format("%s/%s:%s", var.research_image_registry, var.research_image, var.research_image_version)
  openai_location    = var.openai_location != null ? var.openai_location : var.location
  needs_openai_kv    = local.openai_location != var.location
  uses_tf_backend    = var.tfstate_resource_group != null
  firewall_required_domains = [
    "blindchargingapi.eastus.data.azurecr.io",
    "blindchargingapi.azurecr.io",
    "azurecr.io",
  ]
  firewall_custom_outbound = length(var.firewall_allowed_domains) > 0
}
