"""Check the upload contract without starting Spark or contacting Azure."""

import ast
from dataclasses import replace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("existing_job", [False, True])
def test_job_deployment_applies_bounded_task_retries(tmp_path, existing_job):
    from databricks.sdk.service.jobs import BaseJob, JobSettings

    from provisioner.config import load_settings
    from provisioner.databricks import deploy_serverless_job

    settings = load_settings(tmp_path / ".env")
    client = Mock()
    client.jobs.list.return_value = (
        [BaseJob(job_id=952924853382826, settings=JobSettings(name=settings.databricks_job_name))]
        if existing_job
        else []
    )
    client.jobs.create.return_value = Mock(job_id=952924853382826)

    assert deploy_serverless_job(settings, client) == "952924853382826"
    if existing_job:
        client.jobs.create.assert_not_called()
        job = client.jobs.reset.call_args.kwargs["new_settings"].as_dict()
        assert client.jobs.reset.call_args.kwargs["job_id"] == 952924853382826
    else:
        client.jobs.reset.assert_not_called()
        job = JobSettings(**client.jobs.create.call_args.kwargs).as_dict()
    task = job["tasks"][0]
    assert task["max_retries"] == 2
    assert task["min_retry_interval_millis"] == 60_000
    assert task["retry_on_timeout"] is True
    assert task["timeout_seconds"] == 900
    assert job["timeout_seconds"] == 3300


def test_upload_stages_source_in_volume_without_notebook_credentials(tmp_path, monkeypatch):
    from databricks.sdk.service import jobs as job_models

    from provisioner import databricks
    from provisioner.config import load_settings

    settings = replace(
        load_settings(tmp_path / ".env"),
        client_secret="private-secret",
        databricks_host="https://adb.example",
        databricks_token="token",
        storage_account="demostorage",
    )
    client = Mock()
    monkeypatch.setattr(databricks, "download_fixture", lambda *args: b"sale_id\n1\n")
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: client)
    client.jobs.list.return_value = []
    client.jobs.create.return_value = Mock(job_id=123)
    resources = {"storage_account_key": "private-storage-key"}
    assert databricks.deploy_notebooks(settings, resources) == "123"
    client.secrets.put_secret.assert_not_called()
    assert client.files.upload.call_args.args[0] == settings.volume_path + "/raw/sales.csv"
    assert client.files.upload.call_args.args[1].getvalue() == b"sale_id\n1\n"
    uploads = {call.kwargs["path"]: call.kwargs for call in client.workspace.upload.call_args_list}
    upload = uploads[settings.notebook_path + "/sales_demo"]
    source = upload["content"].decode()
    defaults = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DEFAULT_PARAMETERS" for target in node.targets)
    )
    values = ast.literal_eval(defaults.value)
    assert values["raw_path"] == settings.volume_path + "/raw/sales.csv"
    assert values["table_prefix"] == "workspace.default.analytics_demo_sales"
    assert values["report_path"].startswith(settings.volume_path + "/reports/")
    assert "tenant_id" not in values and "client_id" not in values
    assert "private-secret" not in source
    assert "private-storage-key" not in source
    assert "setup_parameters(spark, dbutils, DEFAULT_PARAMETERS)" in source
    assert upload["path"] == settings.notebook_path + "/sales_demo"
    uploads = {call.kwargs["path"]: call.kwargs for call in client.workspace.upload.call_args_list}
    utility_path = settings.notebook_path + "/utils.py"
    utility = uploads[utility_path]
    assert utility["format"].value == "AUTO"
    assert not utility["content"].startswith(b"# Databricks notebook source")
    assert "from utils import" in source
    assert "private-secret" not in utility["content"].decode()
    job = client.jobs.create.call_args.kwargs
    assert job["name"] == settings.databricks_job_name
    assert job["performance_target"] == job_models.PerformanceTarget.STANDARD
    task = job["tasks"][0]
    assert isinstance(task, job_models.Task)
    assert task.new_cluster is None and task.job_cluster_key is None
    assert task.existing_cluster_id is None
    assert task.notebook_task.notebook_path == settings.notebook_path + "/sales_demo"


def test_deploy_discovers_new_notebooks_and_utilities(tmp_path, monkeypatch):
    from provisioner import databricks
    from provisioner.config import load_settings

    settings = replace(
        load_settings(tmp_path / ".env"), root=tmp_path, databricks_host="https://adb.example", databricks_token="token"
    )
    source = tmp_path / "databricks-etl-pipeline/src/notebooks"
    (source / "extra").mkdir(parents=True)
    (source / "first.py").write_text("# Databricks notebook source\nprint(1)\n")
    (source / "extra/second.py").write_text("# Databricks notebook source\nprint(2)\n")
    (source / "utils.py").write_text("VALUE = 10\n")
    client = Mock()
    monkeypatch.setattr(databricks, "download_fixture", lambda *args: b"sale_id\n1\n")
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: client)
    client.jobs.list.return_value = []
    client.jobs.create.return_value = Mock(job_id=456)
    assert databricks.deploy_notebooks(settings, {"storage_account_key": "test-key"}) == "456"
    uploads = {call.kwargs["path"]: call.kwargs for call in client.workspace.upload.call_args_list}
    assert set(uploads) == {
        settings.notebook_path + "/first",
        settings.notebook_path + "/extra/second",
        settings.notebook_path + "/utils.py",
    }
    assert uploads[settings.notebook_path + "/first"]["format"].value == "SOURCE"
    assert uploads[settings.notebook_path + "/utils.py"]["format"].value == "AUTO"


def test_workspace_client_uses_token(tmp_path, monkeypatch):
    from provisioner import databricks
    from provisioner.config import load_settings

    settings = replace(
        load_settings(tmp_path / ".env"), databricks_host="https://adb.example", databricks_token="private-token"
    )
    constructor = Mock()
    monkeypatch.setattr(databricks, "WorkspaceClient", constructor)
    databricks.workspace_client(settings)
    constructor.assert_called_once_with(host="https://adb.example", token="private-token", auth_type="pat")
