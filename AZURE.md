# Azure setup

This guide covers the Azure access and setup for this repository. Python commands run Terraform for you; students do not need to edit or invoke Terraform directly.

## What gets created

The provisioner creates a resource group, an Azure Storage account with `raw`, `lakehouse`, and `reports` containers, and an Azure Data Factory. The default region is Japan East (`japaneast`). Resource names and region defaults are in [config.py](azure-terraform-provisioner/src/provisioner/config.py); the storage account and factory names come from the root `.env`.

The provisioner reads the storage account key from Terraform's sensitive output to upload and stage data. ADF stores it in a secure linked-service connection string for report export. No Azure credentials are placed in Databricks notebooks. Terraform state contains credentials; keep it private and never commit it.

Contributor can list storage account keys, so no data-plane role assignment is required. The key grants access to this dedicated demo account. See [key permissions](https://learn.microsoft.com/en-us/azure/storage/common/storage-account-keys-manage).

Free Edition notebooks read a managed-volume CSV snapshot and write managed Delta tables. They export Parquet to the volume; ADF copies it through the Databricks Files API into Azure's `reports` container. The Azure `lakehouse` container is retained but unused by this workflow.

Storage and Data Factory can incur Azure charges. Databricks Free Edition is a separate workspace and is not created by Terraform.

## Before you start

You need:

- An Azure subscription where your deployment service principal has **Contributor** access. Contributor can create the demo resources and read the storage account key; it cannot create role assignments.
- Python 3.12 and `uv`, as described in the [README setup](README.md#1-prepare-the-environment).
- An existing Databricks Free Edition workspace and a workspace token for deployment. See the [README configuration steps](README.md#2-configure-env).

No `AZURE_PRINCIPAL_OBJECT_ID` or Storage Blob Data Contributor role assignment is needed.

## Fill in `.env`

From the repository root, copy `.env.example` to `.env` and fill in:

| Variable | Where to find it |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | Azure Portal → **Subscriptions** → your subscription → **Subscription ID**. |
| `AZURE_TENANT_ID` | Azure Portal → **Microsoft Entra ID** → **Overview** → **Tenant ID**. See Microsoft's guide to [subscription and tenant IDs](https://learn.microsoft.com/en-us/azure/azure-portal/get-subscription-tenant-id). |
| `AZURE_CLIENT_ID` | Deployment service principal's **Application (client) ID**. |
| `AZURE_CLIENT_SECRET` | A client secret for that application. Copy its **Value** when created; do not use the Secret ID. |
| `STORAGE_ACCOUNT` | A globally unique name: 3–24 lowercase letters or numbers. Terraform creates it. |
| `DATA_FACTORY` | A globally unique Data Factory name. Terraform creates it. |
| `DATABRICKS_HOST` | Full HTTPS URL shown in your Free Edition workspace browser. |
| `DATABRICKS_TOKEN` | Workspace access token used to upload notebooks and configure the job. |

Keep `.env` private; it is ignored by Git. Do not put the storage key in `.env`. If you have an older `.env`, you can delete `AZURE_PRINCIPAL_OBJECT_ID`; it is no longer used. `DATABRICKS_NOTEBOOK_PATH` already has a default in `.env.example`. The resource group, region, and other defaults are in `config.py`.

If you need to create a service principal and your account is allowed to assign Contributor, Azure CLI can do it like this:

```bash
az login
az account set --subscription "<subscription-id>"
az ad sp create-for-rbac \
  --name "analytics-course-deployer" \
  --role Contributor \
  --scopes "/subscriptions/<subscription-id>"
```

The output's `appId`, `password`, and `tenant` values map to `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID`. Store the password securely; Azure CLI displays it only when created. See Microsoft's [service principal creation guide](https://learn.microsoft.com/en-us/cli/azure/create-an-azure-service-principal-azure-cli?view=azure-cli-latest).

## Provision Azure

Run these commands at the repository root:

```bash
uv sync --locked
uv run solution provision
```

The command downloads and verifies Terraform, then initializes, validates, and applies the configuration. It prints non-secret resource information. You do not need to open `main.tf` or install Terraform yourself.

If an earlier provision attempt failed partway through, keep the same `.env` values and run `uv run solution provision` again after fixing the cause. Terraform will reconcile the partially created resources. If Azure says a storage or factory name is already taken, choose another name in `.env` and provision again.

## Deploy and run

Set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in `.env`, then deploy:

```bash
uv run solution deploy
```

Deployment uploads the ten-row CSV, all notebooks and utilities under `databricks-etl-pipeline/src/notebooks/`, creates or updates the serverless Databricks job, and deploys the ADF pipelines. Deployment stages the Azure CSV into a managed volume. Each deployment resets the source to the ten-row fixture and refreshes the snapshot. ADF executions reuse that snapshot. No Databricks secret scope is required.

Follow [Execute online in the README](README.md#4-execute-online) to run a notebook or start the ADF pipeline. After all Azure and Databricks values are configured, `uv run solution setup` runs provisioning and deployment together.

For the next course step, follow [Load the sales report into Power BI](powerbi-business-report/README.md). Use the exported blob in `reports/sales/report.parquet`; the `lakehouse` container remains unused. See [ADF export troubleshooting](azure-data-factory-pipeline/README.md#troubleshoot-the-transfer) if the blob is missing.

## Clean up

To remove the resource group and its demo data, run:

```bash
uv run solution cleanup --confirm-resource-group rg-analytics-demo
```

If you changed the resource group in `config.py`, use that exact name. Cleanup checks the configured name against Terraform state before destroying resources. It leaves Databricks jobs, notebooks, tables, and volumes. Remove these separately in the workspace and Catalog Explorer.

## Troubleshooting

- **`AuthorizationFailed` for `Microsoft.Authorization/roleAssignments/write`:** the current setup no longer creates role assignments. Run `uv sync --locked` and retry with the updated code. If the error names a different operation, the service principal may lack Contributor access for that operation.
- **Storage requests fail with 403:** confirm the storage account allows Shared Key authorization. Some subscription policies disable it; this teaching setup needs Shared Key because students cannot assign data-plane RBAC roles themselves.
- **Databricks deploy says host or token is missing:** set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in the root `.env`; the host must start with `https://`.
- **Terraform reports a name collision:** storage account and Data Factory names must be globally unique. Change the corresponding `.env` value and rerun provisioning.

- **`CONFIG_NOT_AVAILABLE` for `fs.azure.account.key...`:** serverless does not allow that Spark configuration. Redeploy updated notebooks, which use managed storage. See [supported Spark settings](https://learn.microsoft.com/en-us/azure/databricks/spark/conf).
- **Direct Azure connections fail from Free Edition:** outbound access is restricted. The local deployer stages source data, and ADF exports reports without notebook outbound connections. See [Free Edition limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations).
- **Invalid workspace URL in Azure Databricks Job activity:** Free Edition uses a different workspace domain. This pipeline uses Web activities to start and poll the serverless job through the Jobs API instead.
- **Volume/table permission errors:** the deployer needs volume creation permission in the configured catalog/schema (default `workspace.default`). Notebook users need volume read/write and table creation/access.
- **Manual notebook succeeds but report is absent in Azure:** run `uv run solution run-adf` for the Azure copy. Manual execution writes only the volume report. The single-file export suits this ten-row teaching dataset.

ADF uses the workspace token for Jobs API calls and the secure HTTP linked service for Files API downloads. Activity inputs are hidden in monitoring. Redeploy after rotating the token; restrict access to pipeline definitions to trusted course maintainers.
