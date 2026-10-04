from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.datafactory import models as m

from adf import defs
from adf.connections import (
    CREDENTIAL_NAME,
    LINKED_SERVICE_NAME,
    build_linked_service,
)
from provisioner.storage import credential


def pipeline_names() -> tuple[str, ...]:
    return tuple(pipeline.NAME for pipeline in defs.PIPELINES)


def build_pipelines(settings) -> dict[str, m.PipelineResource]:
    return {pipeline.NAME: pipeline.build_pipeline(settings) for pipeline in defs.PIPELINES}


def factory_client(settings):
    return DataFactoryManagementClient(credential(settings), settings.subscription_id)


def deploy_pipelines(settings, resources):
    client = factory_client(settings)
    args = (settings.resource_group, settings.factory_name)
    client.credentials.create_or_update(
        *args,
        CREDENTIAL_NAME,
        m.CredentialResource(properties=m.ManagedIdentityCredential(resource_id=resources["adf_identity_id"])),
    )
    client.linked_services.create_or_update(*args, LINKED_SERVICE_NAME, build_linked_service(settings, resources))
    for name, pipeline in build_pipelines(settings).items():
        client.pipelines.create_or_update(*args, name, pipeline)
