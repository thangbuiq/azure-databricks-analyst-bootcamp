# Azure setup

Step by step, from a fresh **Azure for Students** account. Run every command from the repository root.

## 0. Install

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli): `brew install azure-cli` (macOS)

```bash
uv sync --locked
cp .env.example .env
```

Keep `.env` private. Never commit it.

## 1. Log in to Azure

```bash
az login
az account show --query "{subscription:id, tenant:tenantId}" -o json
```

Copy both IDs into `.env` as `AZURE_SUBSCRIPTION_ID` and `AZURE_TENANT_ID`.

## 2. Register Azure services (once)

```bash
for p in Microsoft.Storage Microsoft.DataFactory Microsoft.Databricks Microsoft.Authorization; do az provider register -n $p; done
```

## 3. Create the deployment service principal

Replace `<SUBSCRIPTION_ID>`:

```bash
az ad sp create-for-rbac \
    --name bda-provisioner \
    --role Owner \
    --scopes "/subscriptions/$(az account show --query id -o tsv)"
```

Copy the output into `.env`:

| Output | `.env` |
|---|---|
| `appId` | `AZURE_CLIENT_ID` |
| `password` | `AZURE_CLIENT_SECRET` |

`Owner` is needed so Terraform can grant the Databricks connector access to storage. Without it, setup fails with `403 AuthorizationFailed ... roleAssignments/write`.

## 4. Choose resource names

In `.env`:

| Key | Rule |
|---|---|
| `STORAGE_ACCOUNT` | Globally unique, 3-24 lowercase letters/digits, e.g. `bda<yourname>01` |
| `DATA_FACTORY` | Globally unique, letters/digits/`-`, e.g. `bda-factory-<yourname>` |
| `RESOURCE_GROUP` | Keep `rg-analytics-demo` |
| `AZURE_LOCATION` | Keep `japaneast`. Student subscriptions only allow some regions; if you get `RequestDisallowedByAzure`, try `southeastasia`, `eastasia` or `eastus` |

## 5. Databricks workspace

1. Azure Portal → **Create a resource** → **Azure Databricks** → create it in any resource group **other than** `rg-analytics-demo` (cleanup deletes that group).
2. Open the workspace → **Launch Workspace**.
3. Copy the browser URL (`https://adb-....azuredatabricks.net`) into `DATABRICKS_HOST`.
4. Top-right avatar → **Settings** → **Developer** → **Access tokens** → **Generate new token** → copy into `DATABRICKS_TOKEN`.
5. Choose `DATABRICKS_CATALOG` (e.g. `workspace`). Setup creates it if it does not exist.

Your user needs `CREATE STORAGE CREDENTIAL`, `CREATE EXTERNAL LOCATION`, and `CREATE CATALOG` on the metastore (or `USE CATALOG` / `CREATE SCHEMA` on an existing catalog). Workspace creators are usually metastore admins. If setup says permission denied, ask one to grant them in **Catalog Explorer**.

## 6. Deploy

```bash
uv run solution setup
```

Takes a few minutes. It creates the Azure resources, links Databricks to storage, and uploads the notebooks to `DATABRICKS_NOTEBOOK_PATH`.

## 7. Check

- Azure Portal → `rg-analytics-demo`: storage account, Data Factory, access connector.
- Databricks → **Workspace** → **Shared** → `analytics-demo`: notebooks.
- Databricks → **Catalog**: schemas `dm_sales`, `dm_who`.

Then follow [DEMO.md](DEMO.md). The notebooks hard-code `bdastorageaccountmaster` and the `workspace` catalog. Edit those values in the first code cell to match your `.env`.

## Troubleshooting

| Error | Fix |
|---|---|
| `AuthorizationFailed ... roleAssignments/write` | Service principal lacks `Owner`. Run step 3's role again: `az role assignment create --assignee <AZURE_CLIENT_ID> --role Owner --scope /subscriptions/<SUBSCRIPTION_ID>`. Wait 5 minutes, rerun `uv run solution setup` |
| `StorageAccountAlreadyTaken` / name invalid | Change `STORAGE_ACCOUNT` (step 4) |
| `RequestDisallowedByAzure` | Change `AZURE_LOCATION` (step 4) |
| `MissingSubscriptionRegistration` | Run step 2, wait a minute, rerun |
| `invalid_client` / `AADSTS7000215` | Wrong `AZURE_CLIENT_SECRET`. Use `password`, not `appId` |
| Databricks `PERMISSION_DENIED` | Step 5 grants |
| Storage validation `access denied` right after setup | Role is still propagating. Wait 5 minutes, run `uv run solution deploy` |
| Terraform says resources already exist | Rerun `uv run solution setup`. Terraform keeps state in `azure-terraform-provisioner/terraform.tfstate`; do not delete it |

## Reference

PAT authenticates ADF and notebook upload. An **Access Connector managed identity** authenticates Databricks access to storage. Sharing a resource group does not grant storage access. Notebook/job users other than the PAT owner need catalog/schema usage, table, and external-location grants in Catalog Explorer.

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
