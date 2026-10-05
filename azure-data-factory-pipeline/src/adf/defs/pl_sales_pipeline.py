"""Run the deployed Databricks serverless job."""

from azure.mgmt.datafactory import models as m

from adf.connections import LINKED_SERVICE_NAME

NAME = "pl_sales_pipeline"


def build_pipeline(settings) -> m.PipelineResource:
    return m.PipelineResource(
        description="Run the sales ETL job using Databricks serverless compute.",
        concurrency=1,
        activities=[
            m.DatabricksJobActivity(
                name="run_sales_serverless_job",
                linked_service_name=m.LinkedServiceReference(
                    type="LinkedServiceReference", reference_name=LINKED_SERVICE_NAME
                ),
                job_id=settings.databricks_job_id,
            )
        ],
    )
