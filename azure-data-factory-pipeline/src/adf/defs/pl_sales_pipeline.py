"""Optional native ADF pipeline; deployment resolves the notebook path automatically."""

from azure.mgmt.datafactory import models as m

from adf.activities import run_databricks_job
from provisioner.config import notebook_parameters

NAME = "pl_sales_pipeline"


def build_pipeline(settings) -> m.PipelineResource:
    sales = run_databricks_job(
        settings,
        name="sales",
        notebook_path="sales_demo",
        parameters=notebook_parameters(settings),
    )
    return m.PipelineResource(
        description="Run the sales serverless job; notebooks write directly to Azure Storage.",
        concurrency=1,
        activities=[sales],
    )
