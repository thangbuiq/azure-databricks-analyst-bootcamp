import pytest


def test_configuration_loads_before_cloud_validation(tmp_path):
    from provisioner.config import load_settings

    s = load_settings(tmp_path / ".env")
    assert s.poll_seconds > 0


def test_env_path_is_independent_of_cwd(tmp_path, monkeypatch):
    from provisioner.config import load_settings

    env = tmp_path / ".env"
    env.write_text("DATA_FACTORY=example-factory\n")
    monkeypatch.chdir("/")
    assert load_settings(env).factory_name == "example-factory"


def test_missing_cloud_fields_are_reported_together(tmp_path):
    from provisioner.config import load_settings

    with pytest.raises(ValueError) as error:
        load_settings(tmp_path / ".env").validate_cloud()
    assert "AZURE_SUBSCRIPTION_ID" in str(error.value)
    assert "AZURE_CLIENT_SECRET" in str(error.value)


def test_settings_repr_redacts_secrets(tmp_path):
    from provisioner.config import load_settings

    env = tmp_path / ".env"
    env.write_text("AZURE_CLIENT_SECRET=never-print-me\nDATABRICKS_TOKEN=never-print-token\n")
    assert "never-print-me" not in repr(load_settings(env))
    assert "never-print-token" not in repr(load_settings(env))
    assert load_settings(env).databricks_token == "never-print-token"


@pytest.mark.parametrize(
    "line", ["DATABRICKS_NOTEBOOK_PATH=/", "DATABRICKS_NOTEBOOK_PATH=/Shared/../bad", "STORAGE_ACCOUNT=UPPER"]
)
def test_invalid_settings(tmp_path, line):
    from provisioner.config import load_settings

    env = tmp_path / ".env"
    env.write_text(line + "\n")
    with pytest.raises(ValueError):
        load_settings(env)


def test_external_env_keeps_repository_source_root(tmp_path):
    from provisioner.config import load_settings, repository_root

    settings = load_settings(tmp_path / ".env")
    assert settings.root == repository_root()
