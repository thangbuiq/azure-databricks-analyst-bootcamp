"""Shared Databricks connection used by the pipeline definitions."""

from azure.mgmt.datafactory import models as m

LINKED_SERVICE_NAME = "ls_databricks"
CREDENTIAL_NAME = "databricks_identity"


def build_linked_service(settings, resources):
    return m.LinkedServiceResource(
        properties=m.AzureDatabricksLinkedService(
            domain=resources["workspace_url"],
            workspace_resource_id=resources["workspace_resource_id"],
            authentication="MSI",
            credential=m.CredentialReference(type="CredentialReference", reference_name=CREDENTIAL_NAME),
            new_cluster_version=settings.runtime,
            new_cluster_num_of_worker="0",
            new_cluster_node_type=settings.node_type,
            data_security_mode="SINGLE_USER",
            new_cluster_spark_conf={
                "spark.databricks.cluster.profile": "singleNode",
                "spark.master": "local[*, 4]",
            },
            new_cluster_custom_tags={"ResourceClass": "SingleNode"},
            policy_id=settings.policy_id or None,
        )
    )
