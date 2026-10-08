# Azure Databricks analyst bootcamp

[![Azure Databricks](https://img.shields.io/badge/Azure-Databricks-0078D4?style=for-the-badge&logo=microsoftazure)](https://azure.microsoft.com/products/databricks)
[![Databricks](https://img.shields.io/badge/Databricks-Serverless-FF3621?style=for-the-badge&logo=databricks)](https://databricks.com)
[![PySpark](https://img.shields.io/badge/PySpark-Analytics-E25A1C?style=for-the-badge&logo=apachespark)](https://spark.apache.org/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)

**Azure Storage → Azure Databricks serverless → Delta tables → Power BI**, orchestrated with native ADF Job activities.

Students run PySpark online in Databricks. Local Python automates Terraform, Unity Catalog storage setup, linked services and notebook upload.

![Azure Databricks bootcamp architecture](.github/images/architecture.excalidraw.png)

## Configure

```bash
uv sync --locked
cp .env.example .env
```

Preserve an existing `.env`. Fill in [.env.example](.env.example): Azure deployment credentials, `RESOURCE_GROUP`, `AZURE_LOCATION`, `STORAGE_ACCOUNT`, `DATA_FACTORY`, `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, and `DATABRICKS_CATALOG` (an existing Unity Catalog catalog).

Use your existing **Azure Databricks** workspace URL, `https://adb-....azuredatabricks.net`. The workspace is not created by this repository. Resource group/location should match the storage deployment; an existing Terraform deployment must retain its state and resource names.

The deployment service principal needs Owner (Contributor alone fails with `403 roleAssignments/write`). New to Azure? Follow the step-by-step [Azure setup](AZURE.md). The Databricks PAT owner needs `CREATE STORAGE CREDENTIAL`, `CREATE EXTERNAL LOCATION`, and `USE CATALOG` / `CREATE SCHEMA` on the target catalog. A workspace/metastore administrator can grant these.

## Deploy

```bash
uv run solution setup
```

This provisions:

- ADLS Gen2 storage with `raw`, `lakehouse`, and `reports` containers.
- An Access Connector with managed identity and Storage Blob Data Contributor access.
- Unity Catalog storage credential, external locations and `dm_sales` / `dm_who` schemas.
- ADF linked services `ls_azure_databricks_serverless` (PAT) and `ls_azure_storage`.
- All notebooks/utilities under `databricks-etl-pipeline/src/notebooks/`, uploaded to `DATABRICKS_NOTEBOOK_PATH`.

It also uploads the small sales fixture to `raw/sales/sales.csv`. It does not create Databricks jobs or ADF pipelines by default. Use `--with-pipelines` to deploy notebook-path definitions and their jobs automatically. Storage access uses the Access Connector identity, not the PAT or notebook-embedded account keys. Merely placing resources in the same resource group does not grant access.

For an existing deployment, run `uv run solution provision` once to add the connector, then `uv run solution deploy`. Storage role propagation can take a few minutes; rerun deploy if initial storage validation reports access denied. Existing resources created outside this Terraform state must be imported before provisioning; do not recreate or rename an existing data-bearing account.

## Run notebooks and ADF

Open a deployed notebook and select **Serverless → Run All**. The first code cell contains hard-coded paths and table names. Edit them directly if needed; deployment does not rewrite them.

In **ADF Studio**:

1. Add an **Azure Databricks Job** activity.
2. Select `ls_azure_databricks_serverless`.
3. Create/select a Databricks job and configure its notebook task(s), using the uploaded workspace paths and serverless compute.
4. Publish and **Trigger now**, or add a schedule trigger.
5. Open **Monitor → activity output** and follow the Databricks run link for execution details.

Serverless supports the native **Job** activity. ADF still requires a Databricks job; you can create it from ADF Studio. With Python definitions, deployment handles job creation and IDs automatically. No Databricks Web activities are used.

A different student/job run identity needs Unity Catalog grants: `USE CATALOG`, `USE SCHEMA`, `CREATE TABLE`, `SELECT` / `MODIFY` on course tables, `READ FILES` on raw, and `CREATE EXTERNAL TABLE`, `READ FILES` / `WRITE FILES` on lakehouse (read/write on reports). Grant these through Catalog Explorer. Storage firewalls also need to permit serverless access.

For a complete worked example, follow the [WHO demo](DEMO.md): it shows the four notebook transformations, Delta writes, ADF orchestration and Power BI model.

## Simple pipeline deployment

**Add a notebook, give its path, deploy. That's it.** No job IDs, job declarations, registry edits, or provisioner changes.

Create `azure-data-factory-pipeline/src/adf/defs/pl_example.py`:

```python
from azure.mgmt.datafactory import models as m
from adf.activities import run_databricks_job

NAME = "pl_example"


def build_pipeline(settings):
    staging = run_databricks_job(
        settings,
        name="staging",
        notebook_path="who/01_staging",
    )
    country = run_databricks_job(
        settings,
        name="country",
        notebook_path="who/02_dim_country_year",
        after=staging,
    )

    return m.PipelineResource(activities=[staging, country])
```

```bash
uv run solution deploy --with-pipelines
uv run solution run-adf pl_example
```

Paths are relative to `databricks-etl-pipeline/src/notebooks/`, without `.py`. Deployment uploads notebooks, creates/reuses the serverless jobs and wires their IDs into **native ADF Job activities**. `after=staging` makes `country` wait for staging to succeed. The teaching notebooks use hard-coded values, so no parameters are needed.

The included WHO pipeline runs all four tables:

```bash
uv run solution run-adf pl_who_pipeline
```

`pl_master_etl` runs sales then the dummy demo child on success. It also needs no job ID.

Python definitions remain **optional**. Normal `solution deploy` provisions linked services and notebooks without updating pipelines or jobs. You can instead build pipelines and create/select jobs in ADF Studio. `run-adf` accepts Studio-only pipelines too.

`--with-pipelines` updates matching definitions and their repository-owned jobs; it can overwrite Studio edits to those objects. Removed definitions do not delete deployed objects. [More examples](azure-data-factory-pipeline/README.md).

The notebooks use separate Markdown and code cells for locations, transforms, writes and `OPTIMIZE`. Each write prints its table and storage path. They contain no widgets, assertions, or repeated count/display checks. Values are hard-coded for `bdastorageaccountmaster` and the `workspace` catalog; changing `.env` does not change notebook code.

## Data locations

| Data | Azure Storage path | Unity Catalog table |
|---|---|---|
| Sales source | `raw/sales/sales.csv` | — |
| Sales Delta | `lakehouse/dm_sales/sales_bronze`, `sales_silver`, `sales_gold` | `<catalog>.dm_sales.analytics_demo_sales_*` |
| WHO source | `raw/who/global_suicide_rates_real_who_worldbank.csv` | — |
| WHO Delta | `lakehouse/dm_who/<table>` | `<catalog>.dm_who.<table>` |
| Sales Parquet | `reports/sales/` (Spark part files) | — |

Notebooks use `abfss://<container>@<account>.dfs.core.windows.net/...`. Each Delta table has its own directory with a `_delta_log`. These are external Unity Catalog tables in your storage account. Power BI can query the tables through a Databricks SQL warehouse; use [DEMO.md](DEMO.md) for the WHO solution and report examples.

## Checks and cleanup

```bash
uv run prek run --all-files
uv run pytest
uv run solution status YOUR_ADF_RUN_ID
uv run solution cleanup --confirm-resource-group YOUR_RESOURCE_GROUP
```

Cleanup deletes the resource group and its contents, including your Azure Databricks workspace if it shares that group. It does not remove Databricks notebooks, jobs, or Unity Catalog metadata. Remove course tables/locations/credentials separately when retiring the course. Existing legacy jobs, Web pipelines and volume datasets are not automatically deleted by migration.

## Repository

| Folder | Purpose |
|---|---|
| `azure-terraform-provisioner/` | Terraform and Python provisioning |
| `azure-data-factory-pipeline/` | Linked services and optional ADF definitions |
| `databricks-etl-pipeline/src/notebooks/` | Teaching notebooks and shared utilities |
| `powerbi-business-report/` | Reporting notes |

[Azure setup](AZURE.md) · [WHO worked demo](DEMO.md) · [Native ADF Job activity](https://learn.microsoft.com/en-us/azure/data-factory/transform-data-databricks-job) · [Managed identity storage access](https://learn.microsoft.com/en-us/azure/databricks/connect/unity-catalog/cloud-storage/azure-managed-identities)
