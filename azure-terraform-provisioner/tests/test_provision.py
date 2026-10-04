import pytest


def test_terraform_env_keeps_credentials_off_arguments(tmp_path):
    from provisioner.config import load_settings
    from provisioner.terraform import terraform_env

    s = load_settings(tmp_path / ".env")
    env = terraform_env(s)
    assert env["ARM_CLIENT_SECRET"] == s.client_secret
    assert "TF_VAR_client_secret" not in env
    assert env["TF_VAR_resource_group"] == "rg-analytics-demo"


def test_rejects_cleanup_of_wrong_group(tmp_path):
    from provisioner.config import load_settings
    from provisioner.terraform import cleanup_resources

    with pytest.raises(ValueError, match="exact"):
        cleanup_resources(load_settings(tmp_path / ".env"), "some-other-group")


def test_archive_checksum_rejects_tampering():
    from provisioner.terraform import verify_archive

    with pytest.raises(ValueError, match="checksum"):
        verify_archive(b"changed", "0" * 64)


def test_terraform_outputs_are_unwrapped():
    from provisioner.terraform import decode_outputs

    assert decode_outputs('{"workspace_url":{"value":"adb.example"}}') == {"workspace_url": "adb.example"}


def test_cleanup_refuses_state_group_different_from_confirmation(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from provisioner import terraform
    from provisioner.config import Settings, load_settings

    settings = load_settings(tmp_path / ".env")
    monkeypatch.setattr(Settings, "validate_cloud", lambda self: None)
    monkeypatch.setattr(terraform, "resources", lambda settings: {"resource_group": "an-older-group"})
    run = Mock()
    monkeypatch.setattr(terraform, "_run", run)
    with pytest.raises(ValueError, match="state"):
        terraform.cleanup_resources(settings, settings.resource_group)
    assert not any("destroy" in call.args for call in run.call_args_list)
