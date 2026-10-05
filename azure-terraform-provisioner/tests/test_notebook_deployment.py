"""Check the upload contract without starting Spark or contacting Azure."""

import ast
from dataclasses import replace
from unittest.mock import Mock


def test_upload_has_interactive_defaults_without_exposing_the_secret(tmp_path, monkeypatch):
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
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: client)
    client.jobs.list.return_value = []
    client.jobs.create.return_value = Mock(job_id=123)
    assert databricks.deploy_notebooks(settings) == "123"
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
    assert values["storage_account"] == "demostorage"
    assert values["raw_path"].endswith("/sales/sales.csv")
    assert "private-secret" not in source
    assert "setup_storage(spark, dbutils, DEFAULT_PARAMETERS)" in source
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
    assert job["performance_target"].value == "STANDARD"
    task = job["tasks"][0]
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
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: client)
    client.jobs.list.return_value = []
    client.jobs.create.return_value = Mock(job_id=456)
    assert databricks.deploy_notebooks(settings) == "456"
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
