from dataclasses import replace
from unittest.mock import MagicMock, Mock


def test_fixture_upload_authenticates_with_storage_key(tmp_path, monkeypatch):
    from provisioner import storage
    from provisioner.config import load_settings

    settings = replace(load_settings(tmp_path / ".env"), storage_account="demostorage")
    fixture = tmp_path / "sales.csv"
    fixture.write_text("id\n1\n")
    service = MagicMock()
    service.__enter__.return_value = service
    blob = service.get_blob_client.return_value
    monkeypatch.setattr(storage, "BlobServiceClient", Mock(return_value=service))

    assert storage.upload_fixture(settings, fixture, "private-key") == (
        "abfss://raw@demostorage.dfs.core.windows.net/sales/sales.csv"
    )
    storage.BlobServiceClient.assert_called_once_with(
        "https://demostorage.blob.core.windows.net", credential="private-key"
    )
    blob.upload_blob.assert_called_once()
