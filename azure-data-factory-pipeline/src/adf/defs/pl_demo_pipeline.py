"""Dummy child pipeline students can replace with their own activity."""

from azure.mgmt.datafactory import models as m

NAME = "pl_demo_pipeline"


def build_pipeline(settings) -> m.PipelineResource:
    demo = m.WaitActivity(name="demo_step", wait_time_in_seconds=1)
    return m.PipelineResource(
        description="Dummy example: wait one second.",
        activities=[demo],
    )
