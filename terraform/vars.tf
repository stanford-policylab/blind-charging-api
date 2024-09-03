variable "subscription_id" {
  type        = string
  description = "Azure subscription ID to deploy to. The subscription must be set up before running Terraform."
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

variable "azure_env" {
  type        = string
  default     = "usgovernment"
  description = "Azure environment to deploy to. Normally this is GovCloud, but does not have to be."
}

variable "registry_password" {
  type        = string
  sensitive   = true
  description = <<EOF
Password for authenticating with the container registry.

This value is issued from the Computational Policy Lab's Azure Container Registry;
the `blind-charging-api` image is only deployed there, and not in this Terraform configuration.
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
