"""Configure storage, upload notebooks and provision jobs for optional ADF definitions."""

from hashlib import sha256

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service import catalog, jobs, workspace

from provisioner.config import notebook_parameters


def workspace_client(settings, resources=None):
    settings.validate_databricks()
    return WorkspaceClient(host=settings.databricks_host, token=settings.databricks_token, auth_type="pat")


def deploy_notebook_jobs(settings, notebook_paths, client=None):
    """Create/reuse one owned serverless job per workspace notebook path."""
    paths = sorted(set(notebook_paths))
    if not paths:
        return {}
    client = client or workspace_client(settings)
    deployed = {}
    for path in paths:
        scope = f"{settings.subscription_id}/{settings.resource_group}/{settings.factory_name}/{path}"
        identity = sha256(scope.encode()).hexdigest()[:24]
        name = f"adf-notebook-{identity}"
        tags = {"managed_by": "analytics-course", "deployment_key": identity}
        job_settings = jobs.JobSettings(
            name=name,
            tags=tags,
            description=f"Managed by ADF notebook deployment: {path}",
            max_concurrent_runs=1,
            queue=jobs.QueueSettings(enabled=True),
            timeout_seconds=settings.timeout_seconds,
            tasks=[
                jobs.Task(
                    task_key="notebook",
                    notebook_task=jobs.NotebookTask(notebook_path=path, source=jobs.Source.WORKSPACE),
                    timeout_seconds=settings.timeout_seconds,
                    max_retries=0,
                )
            ],
        )
        matches = [job for job in client.jobs.list(name=name) if job.settings and job.settings.name == name]
        if len(matches) > 1:
            raise ValueError(f"Multiple Databricks jobs named {name}; resolve duplicates before deploying")
        if matches:
            match = matches[0]
            if match.settings.tags != tags:
                raise ValueError(f"Databricks job {name} is not managed by this deployment")
            client.jobs.reset(job_id=match.job_id, new_settings=job_settings)
            deployed[path] = str(match.job_id)
        else:
            deployed[path] = str(client.jobs.create(**job_settings.as_shallow_dict()).job_id)
    return deployed


def configure_storage(settings, resources, client=None):
    """Use the Terraform-managed identity for direct ADLS access on serverless."""
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
    for schema in (settings.databricks_schema, "dm_who"):
        try:
            client.schemas.get(f"{settings.databricks_catalog}.{schema}")
        except NotFound:
            client.schemas.create(name=schema, catalog_name=settings.databricks_catalog)


def deploy_notebooks(settings, resources=None):
    """Upload every Python notebook and utility with non-secret storage defaults."""
    client = workspace_client(settings)
    for source_file in sorted(settings.notebook_source_dir.rglob("*.py")):
        source = source_file.read_text()
        is_notebook = source.startswith("# Databricks notebook source")
        relative_path = source_file.relative_to(settings.notebook_source_dir)
        if is_notebook:
            relative_path = relative_path.with_suffix("")
            source = source.replace(
                "DEFAULT_PARAMETERS = {}", "DEFAULT_PARAMETERS = " + repr(notebook_parameters(settings))
            )
        destination = settings.notebook_workspace_path(relative_path.as_posix())
        client.workspace.mkdirs(path=destination.rsplit("/", 1)[0])
        client.workspace.upload(
            path=destination,
            content=source.encode(),
            format=workspace.ImportFormat.SOURCE if is_notebook else workspace.ImportFormat.AUTO,
            **({"language": workspace.Language.PYTHON} if is_notebook else {}),
            overwrite=True,
        )
