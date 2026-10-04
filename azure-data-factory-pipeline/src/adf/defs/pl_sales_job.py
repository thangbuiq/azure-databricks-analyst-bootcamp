"""Complete reference pipeline: run one Databricks notebook."""

from azure.mgmt.datafactory import models as m

from adf.connections import LINKED_SERVICE_NAME
from provisioner.config import notebook_parameters

NAME = "pl_sales_job"


def build_pipeline(settings) -> m.PipelineResource:
    days, seconds = divmod(settings.timeout_seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    timeout = f"{days}.{hours:02}:{minutes:02}:{seconds:02}"

    return m.PipelineResource(
        description="Reference: execute one complete PySpark notebook by workspace path.",
        concurrency=1,
        activities=[
            m.DatabricksNotebookActivity(
                name="run_sales_notebook",
                linked_service_name=m.LinkedServiceReference(
                    type="LinkedServiceReference", reference_name=LINKED_SERVICE_NAME
                ),
                notebook_path=settings.notebook_path,
                base_parameters=notebook_parameters(settings),
                policy=m.ActivityPolicy(timeout=timeout, retry=0),
            )
        ],
    )
