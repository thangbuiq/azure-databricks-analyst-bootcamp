"""Provisioning contracts without Spark or live cloud calls."""

import ast
from dataclasses import replace
from unittest.mock import Mock

import pytest
from databricks.sdk.errors import NotFound
from databricks.sdk.service import catalog

from provisioner import databricks
from provisioner.config import Settings


def test_serverless_jobs_are_created_once_and_reused_by_notebook_path(tmp_path):
    from databricks.sdk.service import jobs

    settings = Settings(root=tmp_path)
    path = settings.notebook_workspace_path("who/01_staging")
    client = Mock()
    client.jobs.list.return_value = []
    client.jobs.create.return_value = jobs.CreateResponse(job_id=123)
    assert databricks.deploy_notebook_jobs(settings, [path, path], client) == {path: "123"}
    client.jobs.create.assert_called_once()
    created = client.jobs.create.call_args.kwargs
    assert created["tasks"][0].notebook_task.notebook_path == path
    assert created["tasks"][0].new_cluster is None
    assert created["tasks"][0].existing_cluster_id is None
    client.jobs.list.return_value = [jobs.BaseJob(job_id=123, settings=jobs.JobSettings(**created))]
    client.jobs.create.reset_mock()
    assert databricks.deploy_notebook_jobs(settings, [path], client) == {path: "123"}
    client.jobs.create.assert_not_called()
    client.jobs.reset.assert_called_once()


def test_job_provisioning_refuses_to_overwrite_an_unowned_job(tmp_path):
    from databricks.sdk.service import jobs

    settings = Settings(root=tmp_path)
    client = Mock()
    client.jobs.list.side_effect = lambda name: [jobs.BaseJob(job_id=123, settings=jobs.JobSettings(name=name))]
    with pytest.raises(ValueError, match="not managed by this deployment"):
        databricks.deploy_notebook_jobs(settings, [settings.notebook_workspace_path("sales_demo")], client)
    client.jobs.reset.assert_not_called()


def test_job_provisioning_refuses_ambiguous_remote_jobs(tmp_path):
    from databricks.sdk.service import jobs

    client = Mock()
    client.jobs.list.side_effect = lambda name: [
        jobs.BaseJob(job_id=number, settings=jobs.JobSettings(name=name)) for number in (1, 2)
    ]
    with pytest.raises(ValueError, match="Multiple Databricks jobs"):
        databricks.deploy_notebook_jobs(Settings(root=tmp_path), ["/Shared/test/notebook"], client)
    client.jobs.create.assert_not_called()
    client.jobs.reset.assert_not_called()


def test_uploads_all_sources_without_jobs_or_staging_files(tmp_path, monkeypatch):
    settings = Settings(root=tmp_path, storage_account="courseaccount")
    source = settings.notebook_source_dir
    (source / "who").mkdir(parents=True)
    (source / "who/staging.py").write_text("# Databricks notebook source\nDEFAULT_PARAMETERS = {}\n")
    (source / "utils.py").write_text("VALUE = 1\n")
    client = Mock()
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: client)
    databricks.deploy_notebooks(settings)
    uploads = {call.kwargs["path"]: call.kwargs for call in client.workspace.upload.call_args_list}
    assert set(uploads) == {settings.notebook_path + "/who/staging", settings.notebook_path + "/utils.py"}
    notebook = uploads[settings.notebook_path + "/who/staging"]
    values = ast.literal_eval(ast.parse(notebook["content"]).body[0].value)
    assert values["raw_path"] == "abfss://raw@courseaccount.dfs.core.windows.net/sales/sales.csv"
    assert values["who_lakehouse_path"] == "abfss://lakehouse@courseaccount.dfs.core.windows.net/dm_who"
    assert not any("token" in name or "secret" in name for name in values)
    assert notebook["format"].value == "SOURCE"
    assert uploads[settings.notebook_path + "/utils.py"]["format"].value == "AUTO"
    assert client.jobs.mock_calls == []
    assert client.files.mock_calls == []
    assert client.volumes.mock_calls == []


def test_storage_setup_creates_identity_locations_and_schemas(tmp_path):
    settings = Settings(root=tmp_path, storage_account="courseaccount")
    client = Mock()
    for api in (client.storage_credentials, client.external_locations, client.schemas):
        api.get.side_effect = NotFound("missing")
    databricks.configure_storage(settings, {"databricks_access_connector_id": "/connector"}, client)
    credential = client.storage_credentials.create.call_args.kwargs
    assert credential["azure_managed_identity"].access_connector_id == "/connector"
    assert [c.kwargs["url"] for c in client.external_locations.create.call_args_list] == [
        settings.storage_url(name) for name in ("raw", "lakehouse", "reports")
    ]
    assert [c.kwargs["name"] for c in client.schemas.create.call_args_list] == ["dm_sales", "dm_who"]


def test_storage_setup_preserves_matching_existing_objects(tmp_path):
    settings = Settings(root=tmp_path, storage_account="courseaccount")
    client = Mock()
    client.storage_credentials.get.return_value = catalog.StorageCredentialInfo(
        azure_managed_identity=catalog.AzureManagedIdentityResponse(access_connector_id="/connector")
    )
    client.external_locations.get.side_effect = [
        catalog.ExternalLocationInfo(
            url=settings.storage_url(name) + "/", credential_name=settings.storage_credential_name
        )
        for name in ("raw", "lakehouse", "reports")
    ]
    databricks.configure_storage(settings, {"databricks_access_connector_id": "/connector"}, client)
    client.storage_credentials.create.assert_not_called()
    client.external_locations.create.assert_not_called()
    client.schemas.create.assert_not_called()


def test_storage_setup_refuses_conflicting_identity(tmp_path):
    settings = Settings(root=tmp_path, storage_account="courseaccount")
    client = Mock()
    client.storage_credentials.get.return_value = catalog.StorageCredentialInfo(
        azure_managed_identity=catalog.AzureManagedIdentityResponse(access_connector_id="/someone-else")
    )
    with pytest.raises(ValueError, match="different Access Connector"):
        databricks.configure_storage(settings, {"databricks_access_connector_id": "/connector"}, client)
    client.storage_credentials.update.assert_not_called()
    client.external_locations.create.assert_not_called()


def test_storage_setup_requires_terraform_connector_output(tmp_path):
    with pytest.raises(ValueError, match="Access Connector output is missing"):
        databricks.configure_storage(Settings(root=tmp_path), {}, Mock())


def test_storage_setup_refuses_conflicting_external_location(tmp_path):
    settings = Settings(root=tmp_path, storage_account="courseaccount")
    client = Mock()
    client.storage_credentials.get.return_value = catalog.StorageCredentialInfo(
        azure_managed_identity=catalog.AzureManagedIdentityResponse(access_connector_id="/connector")
    )
    client.external_locations.get.return_value = catalog.ExternalLocationInfo(
        url="abfss://raw@anotheraccount.dfs.core.windows.net", credential_name=settings.storage_credential_name
    )
    with pytest.raises(ValueError, match="already points to different storage"):
        databricks.configure_storage(settings, {"databricks_access_connector_id": "/connector"}, client)
    client.external_locations.update.assert_not_called()
    client.schemas.create.assert_not_called()


def test_workspace_client_uses_token(tmp_path, monkeypatch):
    from provisioner import databricks
    from provisioner.config import load_settings

    settings = replace(
        load_settings(tmp_path / ".env"),
        databricks_host="https://adb-123.1.azuredatabricks.net",
        databricks_token="private-token",
    )
    constructor = Mock()
    monkeypatch.setattr(databricks, "WorkspaceClient", constructor)
    databricks.workspace_client(settings)
    constructor.assert_called_once_with(
        host="https://adb-123.1.azuredatabricks.net", token="private-token", auth_type="pat"
    )
