"""Upload teaching notebooks and create the serverless ETL job."""

from io import BytesIO

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service import catalog, jobs, workspace

from provisioner.config import notebook_parameters
from provisioner.storage import download_fixture


def workspace_client(settings, resources=None):
    settings.validate_databricks()
    return WorkspaceClient(
        host=settings.databricks_host,
        token=settings.databricks_token,
        auth_type="pat",
    )


def _job_settings(settings):
    return jobs.JobSettings(
        name=settings.databricks_job_name,
        description="Run the course sales notebook on Free Edition serverless compute.",
        max_concurrent_runs=1,
        performance_target=jobs.PerformanceTarget.STANDARD,
        tasks=[
            jobs.Task(
                task_key="sales_etl",
                notebook_task=jobs.NotebookTask(
                    notebook_path=settings.notebook_workspace_path("sales_demo"),
                    base_parameters=notebook_parameters(settings),
                    source=jobs.Source.WORKSPACE,
                ),
            )
        ],
    )


def deploy_serverless_job(settings, client=None):
    """Create or update the notebook job without defining classic cluster compute."""
    client = client or workspace_client(settings)
    job_settings = _job_settings(settings)
    matches = [
        job
        for job in client.jobs.list(name=settings.databricks_job_name)
        if job.settings.name == settings.databricks_job_name
    ]
    if len(matches) > 1:
        raise ValueError(f"More than one Databricks job is named {settings.databricks_job_name!r}")
    if matches:
        job_id = matches[0].job_id
        client.jobs.reset(job_id=job_id, new_settings=job_settings)
        return str(job_id)
    return str(client.jobs.create(**job_settings.as_shallow_dict()).job_id)


def deploy_notebooks(settings, resources=None) -> str:
    """Upload every notebook and utility, then return the serverless job ID."""
    storage_key = (resources or {}).get("storage_account_key")
    if not storage_key:
        raise ValueError("Terraform storage key is missing; run: uv run solution provision")
    client = workspace_client(settings, resources)
    try:
        client.volumes.create(
            catalog_name=settings.databricks_catalog,
            schema_name=settings.databricks_schema,
            name=settings.databricks_volume,
            volume_type=catalog.VolumeType.MANAGED,
        )
    except ResourceAlreadyExists:
        pass
    client.files.create_directory(f"{settings.volume_path}/raw")
    client.files.upload(
        notebook_parameters(settings)["raw_path"],
        BytesIO(download_fixture(settings, storage_key)),
        overwrite=True,
    )
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
    return deploy_serverless_job(settings, client)
