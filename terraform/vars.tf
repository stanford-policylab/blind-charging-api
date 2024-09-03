variable "subscription_id" {
  type = string
}

variable "partner" {
  type = string
}

variable "db_user" {
  type    = string
  default = "bcadmin"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "location" {
  type    = string
  default = "usgovvirginia"
}

variable "azure_env" {
  type    = string
  default = "usgovernment"
}

variable "registry_password" {
  type      = string
  sensitive = true
}

variable "tags" {
  type = map(string)
  default = {
    "environment" = "production"
    "app"         = "raceblind"
  }
}

# NOTE: this should *always* be true in production
# Only disable this when the Azure subscription has not been approved to disable filters,
# and we want to deploy the infrastructure anyway. (It must then be enabled later, or the
# race-blind API will not work as expected.)
variable "disable_content_filter" {
  type    = bool
  default = true
}
