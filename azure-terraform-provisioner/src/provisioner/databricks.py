"""Upload teaching notebooks and deploy declared serverless jobs."""

from io import BytesIO

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service import catalog, jobs, workspace

from adf.defs import discover_jobs
from provisioner.config import notebook_parameters
from provisioner.storage import download_fixture


def workspace_client(settings, resources=None):
    settings.validate_databricks()
    return WorkspaceClient(
        host=settings.databricks_host,
        token=settings.databricks_token,
        auth_type="pat",
    )


def _job_settings(settings, declaration):
    tasks = []
    for task in declaration.tasks:
        tasks.append(
            jobs.Task(
                task_key=task.task_key,
                depends_on=[jobs.TaskDependency(task_key=task.after)] if task.after else None,
                max_retries=settings.databricks_task_retries,
                min_retry_interval_millis=settings.databricks_task_retry_interval_seconds * 1000,
                retry_on_timeout=True,
                timeout_seconds=settings.databricks_task_timeout_seconds,
                notebook_task=jobs.NotebookTask(
                    notebook_path=settings.notebook_workspace_path(task.notebook_path),
                    source=jobs.Source.WORKSPACE,
                ),
            )
        )
    return jobs.JobSettings(
        name=declaration.name,
        description="Run course notebooks on Free Edition serverless compute.",
        max_concurrent_runs=1,
        timeout_seconds=settings.databricks_job_timeout_seconds,
        performance_target=jobs.PerformanceTarget.STANDARD,
        tasks=tasks,
    )


def deploy_serverless_jobs(settings, declarations, client=None):
    """Create or update every declared job and return IDs keyed by job name."""
    client = client or workspace_client(settings)
    deployed = {}
    for declaration in declarations:
        job_settings = _job_settings(settings, declaration)
        matches = [job for job in client.jobs.list(name=declaration.name) if job.settings.name == declaration.name]
        if len(matches) > 1:
            raise ValueError(f"More than one Databricks job is named {declaration.name!r}")
        if matches:
            job_id = matches[0].job_id
            client.jobs.reset(job_id=job_id, new_settings=job_settings)
        else:
            job_id = client.jobs.create(**job_settings.as_shallow_dict()).job_id
        deployed[declaration.name] = str(job_id)
    return deployed


def deploy_notebooks(settings, resources, pipelines):
    """Upload every notebook and utility, then deploy jobs declared by the pipelines."""
    storage_key = (resources or {}).get("storage_account_key")
    if not storage_key:
        raise ValueError("Terraform storage key is missing; run: uv run solution provision")
    declarations = discover_jobs(pipelines, settings.notebook_source_dir)
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
    return deploy_serverless_jobs(settings, declarations, client)
