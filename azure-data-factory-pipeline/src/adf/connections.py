"""Shared token-authenticated connection to the Free Edition workspace."""

from azure.mgmt.datafactory import models as m

from provisioner.config import notebook_parameters

VOLUME_SERVICE = "ls_databricks_files"
STORAGE_SERVICE = "ls_report_storage"
VOLUME_REPORT = "ds_volume_report"
AZURE_REPORT = "ds_azure_report"


def build_transfer_connections(settings, resources):
    """ADF downloads the finished volume file because Free Edition blocks Azure egress."""
    return {
        VOLUME_SERVICE: m.LinkedServiceResource(
            properties=m.HttpLinkedService(
                url=settings.databricks_host + "/",
                authentication_type="Anonymous",
                auth_headers={
                    "Authorization": {"type": "SecureString", "value": f"Bearer {settings.databricks_token}"}
                },
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


def build_transfer_datasets(settings):
    return {
        VOLUME_REPORT: m.DatasetResource(
            properties=m.BinaryDataset(
                linked_service_name=m.LinkedServiceReference(
                    type="LinkedServiceReference", reference_name=VOLUME_SERVICE
                ),
                location=m.HttpServerLocation(
                    relative_url="api/2.0/fs/files" + notebook_parameters(settings)["report_path"]
                ),
            )
        ),
        AZURE_REPORT: m.DatasetResource(
            properties=m.BinaryDataset(
                linked_service_name=m.LinkedServiceReference(
                    type="LinkedServiceReference", reference_name=STORAGE_SERVICE
                ),
                location=m.AzureBlobStorageLocation(
                    container="reports", folder_path="sales", file_name="report.parquet"
                ),
            )
        ),
    }
