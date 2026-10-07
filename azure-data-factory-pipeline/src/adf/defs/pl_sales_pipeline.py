"""Run the deployed Databricks job and copy its report to Azure."""

from azure.mgmt.datafactory import models as m

from adf.activities import copy_file, run_databricks_job
from adf.connections import AZURE_REPORT, VOLUME_REPORT
from adf.jobs import serverless_job

NAME = "pl_sales_pipeline"
DATABRICKS_JOBS = (serverless_job("course-sales-etl", ("sales_demo",)),)


def build_pipeline(settings, job_ids) -> m.PipelineResource:
    return m.PipelineResource(
        description="Run the serverless notebook, then copy its Parquet report from the volume to Azure.",
        concurrency=1,
        activities=[
            *run_databricks_job(settings, name="sales", job_id=job_ids[DATABRICKS_JOBS[0].name]),
            copy_file(
                name="copy_report_to_azure",
                source=VOLUME_REPORT,
                destination=AZURE_REPORT,
                after="sales_check",
            ),
        ],
    )
