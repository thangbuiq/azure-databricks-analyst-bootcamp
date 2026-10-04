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
        storage_account="demostorage",
    )
    client = Mock()
    client.service_principals.list.return_value = [Mock(id="10")]
    client.workspace.get_status.return_value = Mock(object_id=22)
    monkeypatch.setattr(databricks, "workspace_client", lambda *args: client)
    databricks.deploy_notebook(settings, {"adf_client_id": "adf-id"})
    upload = client.workspace.upload.call_args.kwargs
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
    assert "DEFAULT_PARAMETERS.get(name" in source
    assert upload["path"] == settings.notebook_path
    assert client.secrets.put_acl.call_args.kwargs["principal"] == "adf-id"
