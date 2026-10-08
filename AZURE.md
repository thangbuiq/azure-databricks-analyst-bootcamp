# Azure setup

Use an existing **Azure Databricks serverless workspace** and a Unity Catalog catalog. The provisioner does not create the workspace.

## Root `.env`

Copy [.env.example](.env.example) only if `.env` does not already exist.

| Input | Value |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | Azure Portal → Subscriptions → ID |
| `AZURE_TENANT_ID` | Microsoft Entra ID → Tenant ID |
| `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Deployment app's client ID and secret **value** |
| `RESOURCE_GROUP`, `AZURE_LOCATION` | Deployment resource group and region |
| `STORAGE_ACCOUNT`, `DATA_FACTORY` | Azure resource names; preserve names already in Terraform state |
| `DATABRICKS_HOST` | `https://adb-....azuredatabricks.net` |
| `DATABRICKS_TOKEN` | PAT of the Databricks deployment user |
| `DATABRICKS_CATALOG` | Existing catalog name from Catalog Explorer |
| `DATABRICKS_NOTEBOOK_PATH` | Upload folder, default `/Shared/analytics-demo` |

## Permissions

- Azure deployer: **Contributor** for resources, plus **Owner** or **User Access Administrator** at the storage scope to assign the connector's role.
- Databricks deployer: permission to upload notebooks, create storage credentials/external locations, and create schemas in the selected catalog.
- Notebook/job users: catalog/schema usage, table creation/read/write, and file/external-table privileges on the external locations. The PAT owner initially owns the locations and schemas created by deployment; other users need grants in Catalog Explorer.

PAT authenticates ADF and notebook upload. An **Access Connector managed identity** authenticates Databricks access to storage. Sharing a resource group does not grant storage access.

## Provision and deploy

```bash
uv sync --locked
uv run solution provision
uv run solution deploy
```

Or run `uv run solution setup` for both steps.

Terraform manages the resource group, HNS-enabled ADLS account, `raw`/`lakehouse`/`reports` containers, ADF, Access Connector, and its Storage Blob Data Contributor assignment. Keep Terraform state and `.env` private. Existing resources outside this state require import before applying; do not replace an existing storage account to adopt it.

Deployment creates/reuses a Unity Catalog credential and three external locations, creates `dm_sales` and `dm_who`, uploads notebooks, and provisions ADF linked services. Existing locations/credentials with conflicting settings cause an error instead of being changed.

Role assignments can take a few minutes to propagate. If Databricks rejects initial storage validation, wait and rerun `solution deploy`. Storage firewalls must permit serverless access. See [managed identity configuration](https://learn.microsoft.com/en-us/azure/databricks/connect/unity-catalog/cloud-storage/azure-managed-identities).

## Execute

Run notebooks online or create a native **Databricks Job** activity in ADF Studio using `ls_azure_databricks_serverless`. Create/select the serverless job and notebook tasks there. Or define `run_databricks_job(settings, name="who", notebook_path="who/01_staging")` in a `pl_*.py` file and run `solution deploy --with-pipelines`: deployment creates/reuses the job and resolves its ID automatically. Python pipeline files are optional.

Raw reads use `abfss://raw@<account>.dfs.core.windows.net/...`; Delta tables use `abfss://lakehouse@<account>.dfs.core.windows.net/<schema>/<table>`. [WHO example](DEMO.md).

## Cleanup

```bash
uv run solution cleanup --confirm-resource-group YOUR_RESOURCE_GROUP
```

This deletes the resource group and its contents, including any Azure Databricks workspace you placed in that same group. Databricks notebooks, saved jobs and Unity Catalog metadata are separate and remain until removed explicitly.
