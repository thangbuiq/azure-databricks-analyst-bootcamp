"""Upload the deterministic source fixture with the demo storage account key."""

import time

from azure.core.exceptions import HttpResponseError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient


def credential(settings):
    """Authenticate Azure management clients with the deployment service principal."""
    return ClientSecretCredential(settings.tenant_id, settings.client_id, settings.client_secret)


def download_fixture(settings, storage_account_key):
    """Read the Azure source snapshot that deployment stages in a managed volume."""
    with BlobServiceClient(
        f"https://{settings.storage_account}.blob.core.windows.net", credential=storage_account_key
    ) as service:
        return service.get_blob_client("raw", "sales/sales.csv").download_blob().readall()


def upload_fixture(settings, fixture_path, storage_account_key):
    with BlobServiceClient(
        f"https://{settings.storage_account}.blob.core.windows.net", credential=storage_account_key
    ) as service:
        client = service.get_blob_client("raw", "sales/sales.csv")
        for attempt in range(12):
            try:
                with fixture_path.open("rb") as stream:
                    client.upload_blob(stream, overwrite=True)
                break
            except HttpResponseError as error:
                if error.status_code not in (403, 429, 503) or attempt == 11:
                    raise
                time.sleep(10)
    return f"abfss://raw@{settings.storage_account}.dfs.core.windows.net/sales/sales.csv"
