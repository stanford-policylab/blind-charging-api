#!/usr/bin/env bash

usage () {
cat << EOF
Usage: $0 <path-to-tfvars-file>

This script initializes the Terraform state store in Azure.

The remote state store is used to store the Terraform state file in Azure Blob Storage.

Arguments:
  <path-to-tfvars-file>  The path to the .tfvars file used for your Blind Charging deployment.
EOF
}

# Initialize the Terraform state store in Azure.
# Modified from https://learn.microsoft.com/en-us/azure/developer/terraform/store-state-in-azure-storage?tabs=azure-cli

# Make sure the Azure CLI is installed.
if ! command -v az &> /dev/null; then
  echo "Azure CLI is not installed. Please install the Azure CLI before running this script."
  exit 1
fi

# The first argument in the script should be the path to the .tfvars file.
# If the argument is not provided, print the usage and exit.
if [ -z "$1" ]; then
  usage
  exit 1
fi

# Check if the .tfvars file exists.
if [ ! -f "$1" ]; then
  echo "The .tfvars file does not exist. Please provide the path to the .tfvars file."
  exit 1
fi

# Load the .tfvars file.
# To do this, we will filter to lines containing variables of interest,
# then remove whitespace around the `=`, then source the output.
VARS=$(grep -E '^(location|partner|subscription_id|tfstate_resource_group)\s*=' $1 | sed 's/ *= */=/')
eval "$VARS"
echo "Loaded variables from $1"

# Check if the `tfstate_resource_group` variable is set.
if [ -z "$tfstate_resource_group" ]; then
  echo "The tfstate_resource_group variable is not set in the .tfvars file."
  exit 1
fi

# Create the storage account name in the format `rbc-<partner>-tfstate`.
# This must be globally unique.
STORAGE_ACCOUNT=$partner'rbctfstate'
# Container name is not configurable right now.
CONTAINER_NAME="tfstate"

echo "Initializing Terraform state storage in Azure if necessary ..."
# Ensure that we're in the correct subscription.
az account set --subscription $subscription_id
# Create the resource group if it doesn't exist.
az group show --name $tfstate_resource_group &> /dev/null || \
  az group create --name $tfstate_resource_group --location $location
# Create the storage account if it doesn't exist.
az storage account show --name $STORAGE_ACCOUNT --resource-group $tfstate_resource_group &> /dev/null || \
  az storage account create --name $STORAGE_ACCOUNT --resource-group $tfstate_resource_group --location $location --sku Standard_LRS --encryption-services blob
# Create the container if it doesn't exist
az storage container show --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT &> /dev/null || \
  az storage container create --name $CONTAINER_NAME --account-name $STORAGE_ACCOUNT

echo "The Terraform state store has been initialized in Azure."
echo
echo "Resource group: $tfstate_resource_group"
echo "Storage account: $STORAGE_ACCOUNT"
echo "Container name: $CONTAINER_NAME"

# Output an AzureRM backend HCL block for the Terraform configuration
# in the same directory as this script.
BASEDIR=$(dirname "$0")
BACKEND_FILE="$BASEDIR/azure.hcl"
cat << EOF > "$BACKEND_FILE"
resource_group_name  = "$tfstate_resource_group"
storage_account_name = "$STORAGE_ACCOUNT"
container_name       = "$CONTAINER_NAME"
key                  = "terraform.tfstate"
EOF

echo
echo "The AzureRM backend configuration has been written to $BACKEND_FILE."
echo
echo "To use it, run:"
echo "  terraform init -backend-config=$BACKEND_FILE"
