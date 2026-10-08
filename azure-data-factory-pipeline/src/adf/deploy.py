from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.datafactory import models as m

from adf import defs
from adf.activities import NotebookJobActivity
from adf.connections import build_connections
from provisioner.databricks import deploy_notebook_jobs
from provisioner.storage import credential


def pipeline_names(pipelines=None) -> tuple[str, ...]:
    pipelines = defs.discover_pipelines() if pipelines is None else pipelines
    return tuple(pipeline.NAME for pipeline in pipelines)


def build_pipelines(settings, pipelines=None) -> dict[str, m.PipelineResource]:
    pipelines = defs.discover_pipelines() if pipelines is None else pipelines
    return {pipeline.NAME: pipeline.build_pipeline(settings) for pipeline in pipelines}


def factory_client(settings):
    return DataFactoryManagementClient(credential(settings), settings.subscription_id)


def _notebook_activities(activities):
    for activity in activities or ():
        if isinstance(activity, NotebookJobActivity):
            yield activity
        for field in ("activities", "if_true_activities", "if_false_activities", "default_activities"):
            yield from _notebook_activities(getattr(activity, field, None))
        for case in getattr(activity, "cases", None) or ():
            yield from _notebook_activities(case.activities)


def deploy_pipelines(settings, resources, built=None):
    built = built or {}
    activities = [activity for pipeline in built.values() for activity in _notebook_activities(pipeline.activities)]
    job_ids = deploy_notebook_jobs(settings, [activity.notebook_path for activity in activities])
    for activity in activities:
        activity.job_id = job_ids[activity.notebook_path]
    client = factory_client(settings)
    args = (settings.resource_group, settings.factory_name)
    for name, connection in build_connections(settings, resources).items():
        client.linked_services.create_or_update(*args, name, connection)
    for name, pipeline in built.items():
        client.pipelines.create_or_update(*args, name, pipeline)
