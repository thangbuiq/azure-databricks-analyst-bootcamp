"""Upload the teaching notebook and configure ADF access."""

from databricks.sdk import AccountClient, WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service import iam, workspace

from provisioner.config import notebook_parameters


def workspace_client(settings, resources):
    return WorkspaceClient(
        host=resources["workspace_url"],
        azure_workspace_resource_id=resources["workspace_resource_id"],
        azure_tenant_id=settings.tenant_id,
        azure_client_id=settings.client_id,
        azure_client_secret=settings.client_secret,
        auth_type="azure-client-secret",
    )


def ensure_adf_identity(settings, resources, client):
    app_id = resources["adf_client_id"]
    matches = list(client.service_principals.list(filter=f'applicationId eq "{app_id}"'))
    if matches:
        principal = matches[0]
    elif settings.account_id:
        account = AccountClient(
            host="https://accounts.azuredatabricks.net",
            account_id=settings.account_id,
            azure_tenant_id=settings.tenant_id,
            azure_client_id=settings.client_id,
            azure_client_secret=settings.client_secret,
            auth_type="azure-client-secret",
        )
        principals = list(account.service_principals.list(filter=f'applicationId eq "{app_id}"'))
        principal = (
            principals[0]
            if principals
            else account.service_principals.create(
                application_id=app_id,
                display_name=f"{settings.factory_name}-databricks",
                active=True,
            )
        )
        account.workspace_assignment.update(
            workspace_id=int(resources["workspace_id"]),
            principal_id=int(principal.id),
            permissions=[iam.WorkspacePermission.USER],
        )
    else:
        try:
            principal = client.service_principals.create(
                application_id=app_id,
                display_name=f"{settings.factory_name}-databricks",
                active=True,
                entitlements=[
                    iam.ComplexValue(value="workspace-access"),
                    iam.ComplexValue(value="allow-cluster-create"),
                ],
            )
        except Exception as exc:
            raise RuntimeError(
                "A Databricks administrator must add the ADF managed identity "
                f"(application ID {app_id}) to this workspace, or set DATABRICKS_ACCOUNT_ID "
                "and grant the deployer account-admin access. See README identity setup."
            ) from exc
    client.service_principals.patch(
        id=principal.id,
        schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        operations=[
            iam.Patch(
                op=iam.PatchOp.ADD,
                path="entitlements",
                value=[{"value": "allow-cluster-create"}],
            )
        ],
    )


def deploy_notebook(settings, resources) -> None:
    client = workspace_client(settings, resources)
    ensure_adf_identity(settings, resources, client)
    try:
        client.secrets.create_scope(scope=settings.secret_scope)
    except ResourceAlreadyExists:
        pass
    client.secrets.put_secret(
        scope=settings.secret_scope,
        key="storage-client-secret",
        string_value=settings.client_secret,
    )
    client.secrets.put_acl(
        scope=settings.secret_scope,
        principal=resources["adf_client_id"],
        permission=workspace.AclPermission.READ,
    )
    client.workspace.mkdirs(path=settings.notebook_path.rsplit("/", 1)[0])
    notebook = settings.root / "databricks-etl-pipeline/src/notebooks/sales_demo.py"
    source = notebook.read_text()
    marker = "DEFAULT_PARAMETERS = {}"
    if source.count(marker) != 1:
        raise ValueError("Notebook default-parameter marker is missing or duplicated")
    source = source.replace(marker, "DEFAULT_PARAMETERS = " + repr(notebook_parameters(settings)))
    client.workspace.upload(
        path=settings.notebook_path,
        content=source.encode(),
        format=workspace.ImportFormat.SOURCE,
        language=workspace.Language.PYTHON,
        overwrite=True,
    )
    info = client.workspace.get_status(path=settings.notebook_path)
    client.workspace.update_permissions(
        workspace_object_type="notebooks",
        workspace_object_id=str(info.object_id),
        access_control_list=[
            workspace.WorkspaceObjectAccessControlRequest(
                service_principal_name=resources["adf_client_id"],
                permission_level=workspace.WorkspaceObjectPermissionLevel.CAN_RUN,
            )
        ],
    )
