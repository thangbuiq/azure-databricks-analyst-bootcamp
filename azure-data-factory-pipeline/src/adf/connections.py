"""Native Azure Databricks serverless and Azure Storage linked services."""

from azure.mgmt.datafactory import models as m

DATABRICKS_SERVICE = "ls_azure_databricks_serverless"
STORAGE_SERVICE = "ls_azure_storage"


def build_connections(settings, resources):
    return {
        DATABRICKS_SERVICE: m.LinkedServiceResource(
            properties=m.AzureDatabricksLinkedService(
                domain=settings.databricks_host,
                access_token=m.SecureString(value=settings.databricks_token),
                # Serverless Job activities have no existing/new cluster settings.
            )
        ),
        STORAGE_SERVICE: m.LinkedServiceResource(
            properties=m.AzureBlobStorageLinkedService(
                connection_string=m.SecureString(
                    value=f"DefaultEndpointsProtocol=https;AccountName={settings.storage_account};"
                    f"AccountKey={resources['storage_account_key']};EndpointSuffix=core.windows.net"
                )
            )
        ),
    }
