from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.datafactory import models as m

from adf import defs
from adf.connections import (
    build_transfer_connections,
    build_transfer_datasets,
)
from provisioner.storage import credential


def pipeline_names(pipelines=None) -> tuple[str, ...]:
    pipelines = defs.discover_pipelines() if pipelines is None else pipelines
    return tuple(pipeline.NAME for pipeline in pipelines)


def build_pipelines(settings, job_ids, pipelines=None) -> dict[str, m.PipelineResource]:
    pipelines = defs.discover_pipelines() if pipelines is None else pipelines
    return {pipeline.NAME: pipeline.build_pipeline(settings, job_ids) for pipeline in pipelines}


def factory_client(settings):
    return DataFactoryManagementClient(credential(settings), settings.subscription_id)


def deploy_pipelines(settings, resources, job_ids, pipelines=None):
    built = build_pipelines(settings, job_ids, pipelines)
    client = factory_client(settings)
    args = (settings.resource_group, settings.factory_name)
    for name, connection in build_transfer_connections(settings, resources).items():
        client.linked_services.create_or_update(*args, name, connection)
    for name, dataset in build_transfer_datasets(settings).items():
        client.datasets.create_or_update(*args, name, dataset)
    for name, pipeline in built.items():
        client.pipelines.create_or_update(*args, name, pipeline)
