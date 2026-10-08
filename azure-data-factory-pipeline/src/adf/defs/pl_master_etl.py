"""Run the sales notebook pipeline, then the dummy pipeline on success."""

from azure.mgmt.datafactory import models as m

from adf.activities import execute_pipeline
from adf.defs.pl_demo_pipeline import NAME as DEMO_PIPELINE
from adf.defs.pl_sales_pipeline import NAME as SALES_PIPELINE

NAME = "pl_master_etl"
PIPELINE_DEPENDENCIES = (SALES_PIPELINE, DEMO_PIPELINE)


def build_pipeline(settings) -> m.PipelineResource:
    sales = execute_pipeline(name="run_sales", pipeline=SALES_PIPELINE)
    demo = execute_pipeline(name="run_demo", pipeline=DEMO_PIPELINE, after=sales)

    return m.PipelineResource(
        description="Master ETL: sales must succeed before the demo pipeline starts.",
        concurrency=1,
        activities=[sales, demo],
    )
