# Azure setup

This guide explains the Azure access and setup needed for this repository. Azure resources are created and configured by the Python provisioner and Terraform; you do not need to edit or run Terraform commands yourself.

## What gets created

The provisioner creates the resource group, an Azure Storage account with `raw`, `lakehouse`, and `reports` containers, the storage role assignment, and an Azure Data Factory. The default region, resource group, and factory name are in [config.py](azure-terraform-provisioner/src/provisioner/config.py). The storage account and Data Factory names come from your root `.env`.

This does not create a Databricks workspace. Use your existing Databricks Free Edition workspace. Azure Storage and Data Factory can incur charges; delete the demo resource group when you finish.

## Before you start

You need:

- An Azure subscription with permission to create a resource group, Storage, and Data Factory.
- A deployment service principal. It needs `Contributor` access to create resources and permission to assign the Storage Blob Data Contributor role. That role assignment permission is commonly provided by `Owner`, `User Access Administrator`, or `Role Based Access Control Administrator` at the subscription scope. `Contributor` alone cannot create role assignments. Ask your Azure administrator or course instructor to prepare this identity if you do not manage subscription access. See [Azure built-in roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/privileged).
- Python 3.12 and `uv`, as described in the [README setup](README.md#1-prepare-the-environment).

The service principal's credentials are used by the provisioner. The provisioner also grants that principal Storage Blob Data Contributor on the demo storage account so deployment can upload the sample data.

## Collect the Azure values

Copy `.env.example` to `.env` from the repository root. Fill the Azure entries below; keep `.env` private and do not commit it.

| `.env` variable | Where to get it |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | Azure Portal → **Subscriptions** → your subscription → **Subscription ID**. |
| `AZURE_TENANT_ID` | Azure Portal → **Microsoft Entra ID** → **Overview** → **Tenant ID**. The [Azure portal guide](https://learn.microsoft.com/en-us/azure/azure-portal/get-subscription-tenant-id) shows both IDs. |
| `AZURE_CLIENT_ID` | App registrations → Overview → **Application (client) ID** |
| `AZURE_CLIENT_SECRET` | App registrations → Certificates & secrets → new secret → copy **Value** |
| `AZURE_PRINCIPAL_OBJECT_ID` | Enterprise applications → select app → Object ID (or az ad sp show --id <CLIENT_ID> --query objectId) |
| `STORAGE_ACCOUNT` | Storage accounts → Overview → Name (or --name used when creating). |
| `DATA_FACTORY` | Data factories → Overview → Name (or --name used when creating). |

Do not create the storage account or Data Factory manually. Terraform creates them using the names in `.env`; a name collision means you should choose another name.

For an administrator creating a service principal with Azure CLI, the following creates one with Contributor at subscription scope. The admin must also grant it one of the role-assignment permissions listed above. The command prints a client secret once, so store it securely:

```bash
az login
az account set --subscription "<subscription-id>"
az ad sp create-for-rbac \
  --name "analytics-course-deployer" \
  --role Contributor \
  --scopes "/subscriptions/<subscription-id>"
```

The output's `appId`, `password`, and `tenant` map to `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID`. To look up the service principal object ID, use:

```bash
az ad sp show --id "<client-id>" --query id -o tsv
```

Put that result in `AZURE_PRINCIPAL_OBJECT_ID`. Azure CLI documents [service principal creation](https://learn.microsoft.com/en-us/cli/azure/create-an-azure-service-principal-azure-cli?view=azure-cli-latest) and [role assignment](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-cli).

## Provision Azure resources

After filling in the Azure values in `.env`, run this at the repository root:

```bash
uv sync --locked
uv run solution provision
```

The command downloads and verifies Terraform, then initializes, validates, and applies the repository's Terraform configuration. It prints the resource group and storage account when provisioning succeeds. You do not need to open `main.tf` or install Terraform separately.

If provisioning fails because the service principal cannot create role assignments, ask the subscription administrator to grant the required access, then run `uv run solution provision` again. If Azure reports that a storage account or factory name is already taken, change that name in `.env` and retry.

## Connect Databricks and deploy

In `.env`, set `DATABRICKS_HOST` to the full HTTPS URL shown in your Free Edition workspace browser and `DATABRICKS_TOKEN` to a workspace access token. Keep the token secret. The remaining notebook path has a working default in `.env.example`.

Deploy the notebooks, sample data, serverless job, and ADF pipeline:

```bash
uv run solution deploy
```

The deployment uploads all notebooks and Python utilities from `databricks-etl-pipeline/src/notebooks/` into `DATABRICKS_NOTEBOOK_PATH`. It then configures the serverless Databricks job and ADF pipeline to run it. For a later one-command provision-and-deploy, use `uv run solution setup` after all Azure and Databricks values are ready.

For running the notebook online and starting the ADF pipeline, follow [Execute online in the README](README.md#4-execute-online). Databricks Free Edition uses serverless compute and has usage limits; see [Free Edition limitations](https://learn.microsoft.com/en-us/azure/databricks/getting-started/free-edition-limitations).

## Remove the demo resources

When you are done, remove the Azure resources and sample data created for this project. Use the resource group name from `config.py` (default: `rg-analytics-demo`):

```bash
uv run solution cleanup --confirm-resource-group rg-analytics-demo
```

If you changed the resource group default in `config.py`, pass that exact name instead. Cleanup checks the confirmation against Terraform state before destroying the managed resources. It does not delete your Databricks Free Edition workspace.

## Common setup errors

- **Permission denied creating a resource or role assignment:** ask the subscription administrator to check the service principal's subscription access. Contributor alone is insufficient for the role assignment.
- **Invalid principal object ID:** use the service principal **Object ID** from Enterprise applications, not the Application (client) ID.
- **Invalid storage account name:** use 3–24 lowercase letters and numbers, with no hyphens, and choose a globally unused name.
- **Databricks deploy says host or token is missing:** set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in the root `.env`. The host must be the full `https://...` workspace URL.
