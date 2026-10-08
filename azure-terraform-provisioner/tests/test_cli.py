import pytest


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


def test_missing_notebook_fails_before_storage_or_azure_writes(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from azure.mgmt.datafactory import models as m

    from adf import defs
    from adf.activities import run_databricks_job
    from provisioner import cli, databricks
    from provisioner.config import Settings

    settings = Settings(
        root=tmp_path, databricks_host="https://adb-123.1.azuredatabricks.net", databricks_token="token"
    )
    pipeline = SimpleNamespace(
        NAME="pl_missing",
        build_pipeline=lambda s: m.PipelineResource(
            activities=[run_databricks_job(s, name="missing", notebook_path="missing")]
        ),
    )
    monkeypatch.setattr(defs, "discover_pipelines", lambda: (pipeline,))
    configure = Mock()
    monkeypatch.setattr(databricks, "configure_storage", configure)
    with pytest.raises(ValueError, match="Notebook does not exist"):
        cli._deploy(settings, {}, with_pipelines=True)
    configure.assert_not_called()


@pytest.mark.parametrize("with_pipelines", [False, True])
def test_deployment_always_provisions_connections_but_pipelines_are_optional(tmp_path, monkeypatch, with_pipelines):
    from unittest.mock import Mock

    from adf import defs
    from adf import deploy as adf_deploy
    from provisioner import cli, databricks, storage
    from provisioner.config import Settings

    settings = Settings(
        root=tmp_path, databricks_host="https://adb-123.1.azuredatabricks.net", databricks_token="token"
    )
    discovery = Mock(return_value=())
    monkeypatch.setattr(defs, "discover_pipelines", discovery)
    configure = Mock()
    upload = Mock()
    monkeypatch.setattr(databricks, "configure_storage", configure)
    monkeypatch.setattr(databricks, "deploy_notebooks", upload)
    monkeypatch.setattr(storage, "upload_fixture", Mock())
    factory = Mock()
    monkeypatch.setattr(adf_deploy, "factory_client", lambda *args: factory)
    result = cli._deploy(settings, {"storage_account_key": "key"}, with_pipelines)
    assert discovery.call_count == int(with_pipelines)
    assert factory.linked_services.create_or_update.call_count == 2
    factory.pipelines.create_or_update.assert_not_called()
    assert "databricks_jobs" not in result
    configure.assert_called_once()
    upload.assert_called_once()
