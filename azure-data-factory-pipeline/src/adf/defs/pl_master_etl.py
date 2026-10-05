"""Run the sales notebook pipeline, then the dummy pipeline on success."""

from azure.mgmt.datafactory import models as m

from adf.defs.pl_demo_pipeline import NAME as DEMO_PIPELINE
from adf.defs.pl_sales_pipeline import NAME as SALES_PIPELINE

NAME = "pl_master_etl"


def build_pipeline(settings) -> m.PipelineResource:
    return m.PipelineResource(
        description="Master ETL: sales must succeed before the demo pipeline starts.",
        concurrency=1,
        activities=[
            m.ExecutePipelineActivity(
                name="run_sales",
                pipeline=m.PipelineReference(type="PipelineReference", reference_name=SALES_PIPELINE),
                wait_on_completion=True,
            ),
            m.ExecutePipelineActivity(
                name="run_demo",
                pipeline=m.PipelineReference(type="PipelineReference", reference_name=DEMO_PIPELINE),
                wait_on_completion=True,
                depends_on=[m.ActivityDependency(activity="run_sales", dependency_conditions=["Succeeded"])],
            ),
        ],
    )
