# Azure setup

This guide covers the Azure access and setup for this repository. Python commands run Terraform for you; students do not need to edit or invoke Terraform directly.

## What gets created

The provisioner creates a resource group, an Azure Storage account with `raw`, `lakehouse`, and `reports` containers, and an Azure Data Factory. The default region is Japan East (`japaneast`). Resource names and region defaults are in [config.py](azure-terraform-provisioner/src/provisioner/config.py); the storage account and factory names come from the root `.env`.

This setup uses the storage account key for the course data. The provisioner reads it from Terraform's sensitive output, uploads the sample CSV with it, and stores it in a Databricks secret scope for the notebook. The key is never put in notebook source, job parameters, or normal command output. Terraform state contains the key, so keep the local state files private and never share or commit them.

An account key can read and write all data in this dedicated demo storage account. Give Databricks secret-scope access only to students who should use the demo data. Microsoft recommends Entra ID authorization for production storage; this key-based approach keeps the course setup within Contributor permissions. Contributor includes permission to list storage account keys ([key permissions](https://learn.microsoft.com/en-us/azure/storage/common/storage-account-keys-manage), [built-in Storage roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/storage)). See also [Shared Key authorization](https://learn.microsoft.com/en-us/rest/api/storageservices/authorize-with-shared-key).

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

Deployment uploads the ten-row CSV, all notebooks and utilities under `databricks-etl-pipeline/src/notebooks/`, creates or updates the serverless Databricks job, and deploys the ADF pipelines. The storage key is saved as a Databricks secret named `storage-account-key` in the configured scope; it is not passed in notebook parameters.

Follow [Execute online in the README](README.md#4-execute-online) to run a notebook or start the ADF pipeline. After all Azure and Databricks values are configured, `uv run solution setup` runs provisioning and deployment together.

## Clean up

To remove the resource group and its demo data, run:

```bash
uv run solution cleanup --confirm-resource-group rg-analytics-demo
```

If you changed the resource group in `config.py`, use that exact name. Cleanup checks the configured name against Terraform state before destroying resources. It does not delete your Databricks workspace.

## Troubleshooting

- **`AuthorizationFailed` for `Microsoft.Authorization/roleAssignments/write`:** the current setup no longer creates role assignments. Run `uv sync --locked` and retry with the updated code. If the error names a different operation, the service principal may lack Contributor access for that operation.
- **Storage requests fail with 403:** confirm the storage account allows Shared Key authorization. Some subscription policies disable it; this teaching setup needs Shared Key because students cannot assign data-plane RBAC roles themselves.
- **Databricks deploy says host or token is missing:** set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in the root `.env`; the host must start with `https://`.
- **Terraform reports a name collision:** storage account and Data Factory names must be globally unique. Change the corresponding `.env` value and rerun provisioning.
