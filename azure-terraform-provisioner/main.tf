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
variable "factory_name" { type = string }

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
resource "azurerm_data_factory" "demo" {
  name                = var.factory_name
  resource_group_name = azurerm_resource_group.demo.name
  location            = var.location
}
output "storage_account" { value = azurerm_storage_account.demo.name }
output "storage_account_key" {
  value     = azurerm_storage_account.demo.primary_access_key
  sensitive = true
}
output "resource_group" { value = azurerm_resource_group.demo.name }
