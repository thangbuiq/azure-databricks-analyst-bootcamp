"""Upload all teaching notebooks and configure ADF access."""

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service import iam, workspace

from provisioner.config import notebook_parameters


def workspace_client(settings, resources):
    settings.validate_databricks()
    return WorkspaceClient(
        host=resources["workspace_url"],
        token=settings.databricks_token,
        auth_type="pat",
    )


def ensure_adf_identity(settings, resources, client):
    app_id = resources["adf_client_id"]
    matches = list(client.service_principals.list(filter=f'applicationId eq "{app_id}"'))
    if matches:
        principal = matches[0]
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
                f"(application ID {app_id}) to this workspace. Use a workspace-admin token for deployment."
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


def deploy_notebooks(settings, resources) -> None:
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
    for source_file in sorted(settings.notebook_source_dir.rglob("*.py")):
        source = source_file.read_text()
        is_notebook = source.startswith("# Databricks notebook source")
        relative_path = source_file.relative_to(settings.notebook_source_dir)
        if is_notebook:
            relative_path = relative_path.with_suffix("")
            # Optional: notebooks using this marker receive non-secret widget defaults.
            source = source.replace(
                "DEFAULT_PARAMETERS = {}", "DEFAULT_PARAMETERS = " + repr(notebook_parameters(settings))
            )
        destination = settings.notebook_workspace_path(relative_path.as_posix())
        client.workspace.mkdirs(path=destination.rsplit("/", 1)[0])
        client.workspace.upload(
            path=destination,
            content=source.encode(),
            format=workspace.ImportFormat.SOURCE if is_notebook else workspace.ImportFormat.AUTO,
            **({"language": workspace.Language.PYTHON} if is_notebook else {}),
            overwrite=True,
        )
        info = client.workspace.get_status(path=destination)
        client.workspace.update_permissions(
            workspace_object_type="notebooks" if is_notebook else "files",
            workspace_object_id=str(info.object_id),
            access_control_list=[
                workspace.WorkspaceObjectAccessControlRequest(
                    service_principal_name=resources["adf_client_id"],
                    permission_level=(
                        workspace.WorkspaceObjectPermissionLevel.CAN_RUN
                        if is_notebook
                        else workspace.WorkspaceObjectPermissionLevel.CAN_READ
                    ),
                )
            ],
        )
