"""Shared token-authenticated connection to the Free Edition workspace."""

from azure.mgmt.datafactory import models as m

LINKED_SERVICE_NAME = "ls_databricks"


def build_linked_service(settings, resources=None):
    return m.LinkedServiceResource(
        properties=m.AzureDatabricksLinkedService(
            domain=settings.databricks_host,
            access_token=m.SecureString(value=settings.databricks_token),
        )
    )
