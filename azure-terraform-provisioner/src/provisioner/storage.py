"""Upload the deterministic source fixture with Entra authentication."""

import time

from azure.core.exceptions import HttpResponseError
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient


def credential(settings):
    return ClientSecretCredential(settings.tenant_id, settings.client_id, settings.client_secret)


def upload_fixture(settings, fixture_path):
    with (
        credential(settings) as auth,
        BlobServiceClient(f"https://{settings.storage_account}.blob.core.windows.net", credential=auth) as service,
    ):
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
