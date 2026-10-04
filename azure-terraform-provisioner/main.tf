terraform {
  required_version = ">= 1.11, < 2.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 4.26.0"
    }
  }
}
provider "azurerm" {
  features {}
}
variable "location" { type = string }
variable "resource_group" { type = string }
variable "storage_account" { type = string }
variable "workspace_name" { type = string }
variable "factory_name" { type = string }
variable "principal_object_id" { type = string }

resource "azurerm_resource_group" "demo" {
  name     = var.resource_group
  location = var.location
  tags     = { purpose = "analytics-course-demo" }
}
resource "azurerm_storage_account" "demo" {
  name                            = var.storage_account
  resource_group_name             = azurerm_resource_group.demo.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}
resource "azurerm_storage_container" "demo" {
  for_each              = toset(["raw", "lakehouse", "reports"])
  name                  = each.value
  storage_account_id    = azurerm_storage_account.demo.id
  container_access_type = "private"
}
resource "azurerm_role_assignment" "storage" {
  scope                = azurerm_storage_account.demo.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.principal_object_id
  principal_type       = "ServicePrincipal"
}
resource "azurerm_databricks_workspace" "demo" {
  name                = var.workspace_name
  resource_group_name = azurerm_resource_group.demo.name
  location            = var.location
  sku                 = "premium"
}
resource "azurerm_user_assigned_identity" "adf" {
  name                = "${var.factory_name}-databricks"
  resource_group_name = azurerm_resource_group.demo.name
  location            = var.location
}
resource "azurerm_data_factory" "demo" {
  name                = var.factory_name
  resource_group_name = azurerm_resource_group.demo.name
  location            = var.location
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.adf.id]
  }
}
output "workspace_url" { value = "https://${azurerm_databricks_workspace.demo.workspace_url}" }
output "workspace_id" { value = azurerm_databricks_workspace.demo.workspace_id }
output "workspace_resource_id" { value = azurerm_databricks_workspace.demo.id }
output "adf_identity_id" { value = azurerm_user_assigned_identity.adf.id }
output "adf_client_id" { value = azurerm_user_assigned_identity.adf.client_id }
output "storage_account" { value = azurerm_storage_account.demo.name }

# ADF's native Databricks linked service requires access to the Azure workspace resource.
resource "azurerm_role_assignment" "adf_databricks" {
  scope                = azurerm_databricks_workspace.demo.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.adf.principal_id
  principal_type       = "ServicePrincipal"
}

output "resource_group" { value = azurerm_resource_group.demo.name }
