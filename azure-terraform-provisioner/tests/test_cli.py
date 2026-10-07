import pytest


def test_build_pipelines_passes_generated_job_ids():
    from types import SimpleNamespace
    from unittest.mock import Mock

    from adf.deploy import build_pipelines

    settings = object()
    job_ids = {"course-who-etl": "123"}
    builder = Mock(return_value="resource")
    pipeline = SimpleNamespace(NAME="pl_who", build_pipeline=builder)

    assert build_pipelines(settings, job_ids, (pipeline,)) == {"pl_who": "resource"}
    builder.assert_called_once_with(settings, job_ids)


def test_deploy_validates_definitions_before_cloud_writes(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from adf import defs
    from adf import deploy as adf_deploy
    from provisioner import cli, databricks, storage

    events = []
    settings = SimpleNamespace(
        root=tmp_path,
        notebook_source_dir=tmp_path / "notebooks",
        databricks_host="https://adb.example",
        notebook_path="/Shared/test",
        validate_databricks=lambda: None,
    )
    pipelines = (SimpleNamespace(NAME="pl_who"),)
    jobs = (SimpleNamespace(name="course-who-etl"),)
    monkeypatch.setattr(defs, "discover_pipelines", lambda: events.append("pipelines") or pipelines)
    monkeypatch.setattr(defs, "discover_jobs", lambda *args: events.append("jobs") or jobs)
    monkeypatch.setattr(storage, "upload_fixture", lambda *args: events.append("fixture"))
    monkeypatch.setattr(
        databricks,
        "deploy_notebooks",
        lambda *args: events.append("databricks") or {"course-who-etl": "123"},
    )
    monkeypatch.setattr(adf_deploy, "deploy_pipelines", lambda *args: events.append(("adf", args[2], args[3])))

    result = cli._deploy(settings, {"storage_account_key": "key"})

    assert events == [
        "pipelines",
        "jobs",
        "fixture",
        "databricks",
        ("adf", {"course-who-etl": "123"}, pipelines),
    ]
    assert result["databricks_jobs"] == {"course-who-etl": "123"}
    assert result["pipelines"] == ["pl_who"]


def test_help_lists_only_cloud_commands(capsys):
    from provisioner.cli import main

    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    for name in ("setup", "deploy", "run-adf", "cleanup"):
        assert name in output
    assert "Run the complete local" not in output
    assert "run-job" not in output


@pytest.mark.parametrize("command", ["--help", "cleanup", "status", "provision"])
def test_administrative_commands_do_not_discover_pipeline_definitions(tmp_path, monkeypatch, capsys, command):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from adf import defs
    from adf import deploy as adf_deploy
    from provisioner import cli, terraform

    discovery = Mock(side_effect=ValueError("Duplicate ADF pipeline name: unfinished"))
    monkeypatch.setattr(defs, "discover_pipelines", discovery)
    settings = SimpleNamespace(validate_cloud=lambda: None, client_secret="", databricks_token="")
    monkeypatch.setattr(cli, "load_settings", lambda *args: settings)
    cleanup = Mock()
    monkeypatch.setattr(terraform, "cleanup_resources", cleanup)
    monkeypatch.setattr(terraform, "provision_resources", lambda *args: {"resource_group": "test-group"})
    monkeypatch.setattr(terraform, "public_resources", lambda resources: resources)
    factory = Mock()
    factory.pipeline_runs.get.return_value = SimpleNamespace(status="Succeeded", message="")
    settings.resource_group = "test-group"
    settings.factory_name = "test-factory"
    monkeypatch.setattr(adf_deploy, "factory_client", lambda *args: factory)

    if command == "--help":
        with pytest.raises(SystemExit) as error:
            cli.main(["--help"])
        assert error.value.code == 0
    else:
        arguments = {
            "cleanup": ["cleanup", "--confirm-resource-group", "test-group"],
            "status": ["status", "run-id"],
            "provision": ["provision"],
        }
        cli.main(arguments[command])
        assert "Error:" not in capsys.readouterr().err
    discovery.assert_not_called()


def test_setup_requires_configuration_before_side_effects(tmp_path, capsys):
    from provisioner.cli import main

    with pytest.raises(SystemExit) as error:
        main(["--env", str(tmp_path / ".env"), "setup"])
    assert error.value.code == 1
    assert "AZURE_CLIENT_SECRET" in capsys.readouterr().err
    assert not (tmp_path / ".runtime").exists()


def test_setup_checks_notebooks_before_provisioning_azure(tmp_path, monkeypatch, capsys):
    from dataclasses import replace
    from unittest.mock import Mock

    from adf import defs
    from adf.jobs import serverless_job
    from provisioner import cli, terraform
    from provisioner.config import Settings

    settings = replace(
        Settings(root=tmp_path),
        subscription_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        client_id="00000000-0000-0000-0000-000000000003",
        client_secret="test-secret",
        storage_account="teststorage",
        databricks_host="https://example.invalid",
        databricks_token="test-token",
    )
    pipeline = Mock(NAME="pl_missing", DATABRICKS_JOBS=(serverless_job("missing-job", ("missing",)),))
    monkeypatch.setattr(cli, "load_settings", lambda *args: settings)
    monkeypatch.setattr(defs, "discover_pipelines", lambda: (pipeline,))
    provision = Mock(side_effect=AssertionError("Azure must not be provisioned for invalid declarations"))
    monkeypatch.setattr(terraform, "provision_resources", provision)

    with pytest.raises(SystemExit) as error:
        cli.main(["setup"])
    assert error.value.code == 1
    provision.assert_not_called()
    assert "Notebook does not exist: missing" in capsys.readouterr().err


def test_new_definition_deploys_notebooks_job_and_adf_without_configuration_changes(tmp_path, monkeypatch):
    from dataclasses import replace
    from unittest.mock import Mock

    from adf import defs
    from adf import deploy as adf_deploy
    from provisioner import cli, databricks, storage
    from provisioner.config import Settings

    settings = replace(Settings(root=tmp_path), databricks_host="https://example.invalid", databricks_token="token")
    notebook_dir = settings.notebook_source_dir / "who"
    notebook_dir.mkdir(parents=True)
    for name in ("01_staging", "02_fact"):
        (notebook_dir / f"{name}.py").write_text("# Databricks notebook source\nprint('lesson')\n")
    package = tmp_path / "new_pipeline_definitions"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "pl_who.py").write_text("""
from azure.mgmt.datafactory import models as m
from adf.jobs import serverless_job
from adf.activities import run_databricks_job
NAME = "pl_who"
DATABRICKS_JOBS = (serverless_job("course-who-etl", ("who/01_staging", "who/02_fact")),)
def build_pipeline(settings, job_ids):
    return m.PipelineResource(activities=[
        *run_databricks_job(settings, name="who", job_id=job_ids[DATABRICKS_JOBS[0].name])
    ])
""")
    monkeypatch.syspath_prepend(str(tmp_path))
    discover = defs.discover_pipelines
    monkeypatch.setattr(defs, "discover_pipelines", lambda: discover("new_pipeline_definitions"))
    workspace = Mock()
    workspace.jobs.list.return_value = []
    workspace.jobs.create.return_value = Mock(job_id=987)
    factory = Mock()
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: workspace)
    monkeypatch.setattr(databricks, "download_fixture", lambda *args: b"sale_id\n1\n")
    monkeypatch.setattr(storage, "upload_fixture", lambda *args: None)
    monkeypatch.setattr(adf_deploy, "factory_client", lambda *args: factory)

    result = cli._deploy(settings, {"storage_account_key": "key"})

    assert result["databricks_jobs"] == {"course-who-etl": "987"}
    assert result["pipelines"] == ["pl_who"]
    uploaded = {call.kwargs["path"] for call in workspace.workspace.upload.call_args_list}
    assert uploaded == {f"{settings.notebook_path}/who/01_staging", f"{settings.notebook_path}/who/02_fact"}
    job_tasks = workspace.jobs.create.call_args.kwargs["tasks"]
    assert job_tasks[1].depends_on[0].task_key == "01_staging"
    deployed = factory.pipelines.create_or_update.call_args.args
    assert deployed[2] == "pl_who"
    assert deployed[3].activities[0].body["job_id"] == 987
