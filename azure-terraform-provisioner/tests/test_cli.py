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


def test_setup_requires_configuration_before_side_effects(tmp_path, capsys):
    from provisioner.cli import main

    with pytest.raises(SystemExit) as error:
        main(["--env", str(tmp_path / ".env"), "setup"])
    assert error.value.code == 1
    assert "AZURE_CLIENT_SECRET" in capsys.readouterr().err
    assert not (tmp_path / ".runtime").exists()
