from dataclasses import replace
from unittest.mock import Mock

import pytest


def test_reference_pipeline_executes_notebook_path_directly(tmp_path):
    from adf.deploy import build_pipelines
    from provisioner.config import load_settings

    s = replace(load_settings(tmp_path / ".env"), notebook_path="/Shared/course/sales_demo")
    pipelines = build_pipelines(s)
    assert set(pipelines) == {"pl_sales_job", "pl_dependency_demo"}
    main = pipelines["pl_sales_job"].serialize()["properties"]
    assert len(main["activities"]) == 1
    notebook = main["activities"][0]
    assert notebook["type"] == "DatabricksNotebook"
    assert notebook["typeProperties"]["notebookPath"] == "/Shared/course/sales_demo"
    assert notebook["linkedServiceName"]["referenceName"] == "ls_databricks"
    assert "WebActivity" not in str(main)
    assert notebook["policy"]["retry"] == 0


def test_dependency_pipeline_waits_for_success(tmp_path):
    from adf.deploy import build_pipelines
    from provisioner.config import load_settings

    pipelines = build_pipelines(load_settings(tmp_path / ".env"))
    demo = pipelines["pl_dependency_demo"].serialize()["properties"]["activities"]
    assert demo[0]["typeProperties"]["waitOnCompletion"] is True
    assert demo[0]["typeProperties"]["pipeline"]["referenceName"] == "pl_sales_job"
    assert demo[1]["dependsOn"] == [{"activity": "run_sales_job", "dependencyConditions": ["Succeeded"]}]


def test_linked_service_uses_managed_identity(tmp_path):
    from adf.connections import build_linked_service
    from provisioner.config import load_settings

    s = replace(load_settings(tmp_path / ".env"), client_secret="never-print-me")
    resource = build_linked_service(s, {"workspace_url": "https://adb.example", "workspace_resource_id": "/workspace"})
    body = resource.serialize()["properties"]["typeProperties"]
    assert body["authentication"] == "MSI"
    assert body["credential"]["referenceName"] == "databricks_identity"
    assert "never-print-me" not in str(body)


@pytest.mark.parametrize("status", ["Failed", "Cancelled"])
def test_adf_failure_propagates(status):
    from adf.runs import wait_for_pipeline_client

    client = Mock()
    client.pipeline_runs.get.return_value = Mock(status=status, message="failure")
    with pytest.raises(RuntimeError):
        wait_for_pipeline_client(client, "rg", "factory", "run-id", 1, 0.01)


def test_adf_success_and_timeout():
    from adf.runs import wait_for_pipeline_client

    client = Mock()
    client.pipeline_runs.get.return_value = Mock(status="Succeeded")
    assert wait_for_pipeline_client(client, "rg", "factory", "id", 1, 0.01).status == "Succeeded"
    client.pipeline_runs.get.return_value = Mock(status="InProgress")
    with pytest.raises(TimeoutError):
        wait_for_pipeline_client(client, "rg", "factory", "id", 0.002, 0.001)


def test_registering_one_module_updates_deployment_run_and_cli(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    from azure.mgmt.datafactory import models as m

    from adf import defs, deploy, runs
    from provisioner.cli import main
    from provisioner.config import load_settings

    example = SimpleNamespace(
        NAME="pl_new_example",
        build_pipeline=lambda settings: m.PipelineResource(
            activities=[m.WaitActivity(name="wait", wait_time_in_seconds=1)]
        ),
    )
    monkeypatch.setattr(defs, "PIPELINES", (*defs.PIPELINES, example))
    with pytest.raises(SystemExit) as exit_info:
        main(["run-adf", "--help"])
    assert exit_info.value.code == 0
    assert example.NAME in capsys.readouterr().out

    settings = load_settings(tmp_path / ".env")
    client = Mock()
    monkeypatch.setattr(deploy, "factory_client", lambda settings: client)
    monkeypatch.setattr(runs, "factory_client", lambda settings: client)
    deploy.deploy_pipelines(
        settings,
        {
            "adf_identity_id": "/identity",
            "workspace_url": "https://adb.example",
            "workspace_resource_id": "/workspace",
        },
    )
    assert client.pipelines.create_or_update.call_args.args[2] == example.NAME
    runs.run_pipeline(settings, example.NAME)
    assert client.pipelines.create_run.call_args.args[2] == example.NAME
