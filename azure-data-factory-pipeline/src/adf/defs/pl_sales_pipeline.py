"""Run the deployed Databricks job and copy its report to Azure."""

from azure.mgmt.datafactory import models as m

from adf.activities import copy_file, run_databricks_job
from adf.connections import AZURE_REPORT, VOLUME_REPORT

NAME = "pl_sales_pipeline"


def build_pipeline(settings) -> m.PipelineResource:
    return m.PipelineResource(
        description="Run the serverless notebook, then copy its Parquet report from the volume to Azure.",
        concurrency=1,
        activities=[
            *run_databricks_job(settings, name="sales", job_id=settings.databricks_job_id),
            copy_file(
                name="copy_report_to_azure",
                source=VOLUME_REPORT,
                destination=AZURE_REPORT,
                after="sales_check",
            ),
        ],
    )
