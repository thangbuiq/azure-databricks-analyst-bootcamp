"""Complete dependency example: wait for the child, then run a dummy activity."""

from azure.mgmt.datafactory import models as m

from adf.defs.pl_sales_job import NAME as CHILD_PIPELINE

NAME = "pl_dependency_demo"


def build_pipeline(settings) -> m.PipelineResource:
    return m.PipelineResource(
        description="Teaching example: child pipeline must succeed before the dummy activity.",
        concurrency=1,
        activities=[
            m.ExecutePipelineActivity(
                name="run_sales_job",
                pipeline=m.PipelineReference(type="PipelineReference", reference_name=CHILD_PIPELINE),
                wait_on_completion=True,
            ),
            m.WaitActivity(
                name="dummy_next_step",
                wait_time_in_seconds=1,
                depends_on=[m.ActivityDependency(activity="run_sales_job", dependency_conditions=["Succeeded"])],
            ),
        ],
    )
