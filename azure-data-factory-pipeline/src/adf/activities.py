"""Reusable steps for Python-defined ADF pipelines."""

from pathlib import PurePosixPath

from azure.mgmt.datafactory import models as m

from adf.connections import DATABRICKS_SERVICE


def _depends_on(after):
    if after is None:
        return []
    dependencies = after if isinstance(after, (list, tuple)) else [after]
    return [
        m.ActivityDependency(
            activity=dependency if isinstance(dependency, str) else dependency.name,
            dependency_conditions=["Succeeded"],
        )
        for dependency in dependencies
    ]


class NotebookJobActivity(m.DatabricksJobActivity):
    """Native activity with a local-only notebook path, resolved before ADF deployment."""

    def __init__(self, *, notebook_path, **kwargs):
        super().__init__(job_id=None, **kwargs)
        self.notebook_path = notebook_path


def run_databricks_job(settings, *, name, notebook_path, parameters=None, after=None):
    """Declare a notebook run; deployment handles the serverless job and its ID."""
    path = PurePosixPath(notebook_path)
    if (
        not notebook_path
        or path.is_absolute()
        or path.as_posix() != notebook_path
        or ".." in path.parts
        or path.suffix == ".py"
    ):
        raise ValueError("notebook_path must be relative to src/notebooks, without .py")
    source = settings.notebook_source_dir / (notebook_path + ".py")
    if not source.is_file() or not source.read_text().startswith("# Databricks notebook source"):
        raise ValueError(f"Notebook does not exist: {notebook_path}")
    return NotebookJobActivity(
        name=name,
        notebook_path=settings.notebook_workspace_path(notebook_path),
        job_parameters=parameters or {},
        linked_service_name=m.LinkedServiceReference(type="LinkedServiceReference", reference_name=DATABRICKS_SERVICE),
        depends_on=_depends_on(after),
        policy=m.ActivityPolicy(timeout="01:00:00", retry=0),
    )


def copy_file(*, name, source, destination, after=None):
    """Copy bytes from an HTTP BinaryDataset to an Azure Blob BinaryDataset by dataset name."""
    return m.CopyActivity(
        name=name,
        depends_on=_depends_on(after),
        source=m.BinarySource(store_settings=m.HttpReadSettings(request_method="GET")),
        sink=m.BinarySink(store_settings=m.AzureBlobStorageWriteSettings()),
        inputs=[m.DatasetReference(type="DatasetReference", reference_name=source)],
        outputs=[m.DatasetReference(type="DatasetReference", reference_name=destination)],
    )


def execute_pipeline(*, name, pipeline, after=None, parameters=None):
    """Run a registered child pipeline and wait for it to finish."""
    return m.ExecutePipelineActivity(
        name=name,
        depends_on=_depends_on(after),
        pipeline=m.PipelineReference(type="PipelineReference", reference_name=pipeline),
        wait_on_completion=True,
        parameters=parameters or {},
    )
