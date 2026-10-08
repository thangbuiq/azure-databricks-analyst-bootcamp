"""Configure Unity Catalog storage access and upload Databricks notebooks."""

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError, NotFound
from databricks.sdk.service import catalog, workspace


def workspace_client(settings, resources=None):
    settings.validate_databricks()
    return WorkspaceClient(host=settings.databricks_host, token=settings.databricks_token, auth_type="pat")


def ensure_catalog(settings, client):
    """Create DATABRICKS_CATALOG when missing; fall back to lakehouse managed storage if the metastore has no root."""
    name = settings.databricks_catalog
    try:
        client.catalogs.get(name)
        return
    except NotFound:
        pass
    try:
        client.catalogs.create(name=name)
    except DatabricksError:
        client.catalogs.create(name=name, storage_root=f"{settings.storage_url('lakehouse')}/_catalogs/{name}")


def configure_storage(settings, resources, client=None):
    """Use the Terraform-managed identity for Databricks direct ADLS access."""
    connector_id = resources.get("databricks_access_connector_id")
    if not connector_id:
        raise ValueError("Access Connector output is missing; run: uv run solution provision")
    client = client or workspace_client(settings)
    credential_name = settings.storage_credential_name
    try:
        credential = client.storage_credentials.get(credential_name)
    except NotFound:
        client.storage_credentials.create(
            name=credential_name,
            azure_managed_identity=catalog.AzureManagedIdentityRequest(access_connector_id=connector_id),
        )
    else:
        identity = credential.azure_managed_identity
        if not identity or identity.access_connector_id.lower() != connector_id.lower():
            raise ValueError(f"Storage credential {credential_name} uses a different Access Connector")

    for container in ("raw", "lakehouse", "reports"):
        name = f"{credential_name}_{container}"
        url = settings.storage_url(container)
        try:
            location = client.external_locations.get(name)
        except NotFound:
            client.external_locations.create(name=name, url=url, credential_name=credential_name)
        else:
            if location.url.rstrip("/") != url or location.credential_name != credential_name:
                raise ValueError(f"External location {name} already points to different storage")
    ensure_catalog(settings, client)
    for schema in (settings.databricks_schema, "dm_who"):
        try:
            client.schemas.get(f"{settings.databricks_catalog}.{schema}")
        except NotFound:
            client.schemas.create(name=schema, catalog_name=settings.databricks_catalog)


def deploy_notebooks(settings, resources=None):
    """Upload every Python notebook and utility exactly as authored."""
    client = workspace_client(settings)
    for source_file in sorted(settings.notebook_source_dir.rglob("*.py")):
        source = source_file.read_text()
        is_notebook = source.startswith("# Databricks notebook source")
        relative_path = source_file.relative_to(settings.notebook_source_dir)
        if is_notebook:
            relative_path = relative_path.with_suffix("")
        destination = settings.notebook_workspace_path(relative_path.as_posix())
        client.workspace.mkdirs(path=destination.rsplit("/", 1)[0])
        client.workspace.upload(
            path=destination,
            content=source.encode(),
            format=workspace.ImportFormat.SOURCE if is_notebook else workspace.ImportFormat.AUTO,
            **({"language": workspace.Language.PYTHON} if is_notebook else {}),
            overwrite=True,
        )
