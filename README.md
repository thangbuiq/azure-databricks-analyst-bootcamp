# azure-databricks-analyst-bootcamp

> A hands-on Medallion-architecture bootcamp repo that takes Data Analysts from raw Azure Blob data to Power BI dashboards, using Databricks Free Edition serverless jobs, Delta Lake, and Azure Data Factory.

---

## Table of Contents

- [azure-databricks-analyst-bootcamp](#azure-databricks-analyst-bootcamp)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Architecture](#architecture)
  - [Orchestration Flow](#orchestration-flow)
  - [Tech Stack](#tech-stack)
  - [Setup and Run from Your Local Machine](#setup-and-run-from-your-local-machine)
    - [1. Prepare the environment](#1-prepare-the-environment)
    - [2. Configure `.env`](#2-configure-env)
    - [3. Provision and deploy](#3-provision-and-deploy)
    - [4. Execute online](#4-execute-online)
    - [5. Format and check deployment code](#5-format-and-check-deployment-code)
    - [6. Clean up Azure resources](#6-clean-up-azure-resources)

---

## Overview

This repository is an end-to-end analytics example for Data Analysts learning the Azure + Databricks ecosystem.

**Pipeline in one sentence:** raw files land in **Azure Blob Storage**, get transformed through a **Bronze → Silver → Gold** Medallion architecture on **Databricks (Spark, Delta Lake)**, the whole thing is orchestrated by **Azure Data Factory (ADF)**, and the Gold layer is exported back to **Blob Storage as Parquet** for **Power BI** to consume as the final BI layer.

Students develop, execute, and test notebooks **online in the Databricks workspace**. Local Python commands handle infrastructure setup and deployment.

---

## Architecture

![Architecture Diagram](.github/images/architecture.excalidraw.png)

| Folder | Responsibility |
|---|---|
| `azure-terraform-provisioner/` | Azure infrastructure managed by Terraform and automated through Python |
| `azure-data-factory-pipeline/` | Complete Python pipeline definitions in `src/adf/defs/` (one file per pipeline), with shared connection and deployment helpers |
| `databricks-etl-pipeline/` | Dummy source data, SQL-based PySpark notebooks and shared write utilities under `src/notebooks/` |
| `powerbi-business-report/` | Power BI reporting layer consuming the exported Parquet data |

See [adding pipeline definitions](azure-data-factory-pipeline/README.md) for the import-and-register workflow.

---

## Orchestration Flow

```mermaid
sequenceDiagram
    participant Parent as Master ADF Pipeline
    participant Child as Notebook ADF Pipeline
    participant Demo as Demo ADF Pipeline
    participant Notebook as Databricks Notebook
    participant Blob as Azure Blob Storage
    participant PBI as Power BI

    Parent->>Child: Execute Pipeline and wait for completion
    Child->>Notebook: Start serverless job through Jobs API
    Note over Notebook,Blob: Deployment stages Azure CSV in a managed volume
    Notebook->>Notebook: Read staged CSV
    Note over Notebook: Bronze → Silver → Gold using Spark and Delta Lake
    Notebook->>Notebook: Write managed Delta tables and volume Parquet
    Notebook-->>Child: Execution result
    Child->>Blob: Copy volume Parquet through Files API
    Child-->>Parent: Success
    Parent->>Demo: Execute Pipeline and wait for completion
    Demo-->>Parent: Execution result
    Note over PBI: Refresh reads the exported Parquet data
```

---

## Tech Stack

| Concern | Technology |
|---|---|
| Infrastructure | Azure Storage and Data Factory provisioned with Terraform through Python |
| Source storage | Azure Blob Storage / ADLS Gen2 |
| Compute / transform | Databricks Free Edition serverless jobs (PySpark notebooks) |
| Storage format | Delta Lake (Bronze/Silver/Gold) |
| Orchestration | Azure Data Factory, configured with Python |
| BI export format | Parquet (Blob Storage) |
| BI / reporting | Power BI |
| Configuration | Essential inputs in root `.env`; defaults in `config.py` |
| Formatting | Prek and Ruff, configured at the repository root |
| CI | GitHub Actions |

---

## Setup and Run from Your Local Machine

### 1. Prepare the environment

Install **Python 3.12** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**. From the repository root:

```bash
uv sync --locked
cp .env.example .env
```

On PowerShell, use `Copy-Item .env.example .env`. Preserve an existing `.env` when updating the repository.

Spark and Delta Lake run in Databricks; local Java and Spark installations are not required. Terraform is downloaded and verified automatically by the provisioning command.

### 2. Configure `.env`

Use [.env.example](.env.example) as the configuration reference. For Azure permissions and step-by-step setup, follow [AZURE.md](AZURE.md). Fill in these values:

| Variable | Description |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_TENANT_ID` | Microsoft Entra tenant ID |
| `AZURE_CLIENT_ID` | Deployment service principal's application/client ID |
| `AZURE_CLIENT_SECRET` | Deployment service principal's secret |
| `STORAGE_ACCOUNT` | Globally unique storage account name: 3-24 lowercase letters/numbers |
| `DATA_FACTORY` | Globally unique Data Factory name |
| `DATABRICKS_HOST` | Full HTTPS URL from your Free Edition workspace browser |
| `DATABRICKS_TOKEN` | Workspace access token used to deploy notebooks and the job |

Set `DATABRICKS_NOTEBOOK_PATH` to a workspace folder such as `/Shared/analytics-demo`. Region, resource group, catalog/schema/volume, table prefix, serverless job name, and timeouts are configured in [config.py](azure-terraform-provisioner/src/provisioner/config.py).

The Azure service principal needs Contributor access. The local provisioner and ADF use the storage account key; notebooks use managed Databricks storage and need no Azure credentials. ADF stores storage credentials in secure linked-service fields.

Free Edition supports serverless compute only. The deployed job leaves cluster settings out so it runs on serverless. Its fair usage limits apply, including the account's job concurrency quota. See [Free Edition limits](https://learn.microsoft.com/en-us/azure/databricks/getting-started/free-edition-limitations).


### 3. Provision and deploy

First provision the Azure storage and Data Factory resources:

```bash
uv run solution provision
```

The command does not create a Databricks workspace. Use your existing Free Edition workspace URL in `DATABRICKS_HOST` and add its token to `DATABRICKS_TOKEN`, then deploy:

```bash
uv run solution deploy
```

Deployment uploads every Python notebook and utility beneath `DATABRICKS_NOTEBOOK_PATH`, uploads the ten-row source CSV to Azure Storage, creates or updates the serverless Databricks job, and configures ADF to run that job. ADF Web activities call the Databricks Jobs API and poll for completion because the Azure Databricks Job activity rejects Free Edition workspace URLs.

The Azure Storage account and Data Factory can incur Azure charges. Free Edition job execution uses Databricks serverless quotas.

For later infrastructure changes and deployment together, `uv run solution setup` requires the Databricks host and token already configured. Terraform retains its state under `azure-terraform-provisioner/`; use that same configuration to clean up resources.


### 4. Execute online

Open the Databricks workspace and a notebook inside the folder configured by `DATABRICKS_NOTEBOOK_PATH`. Select **Serverless** compute, then **Run All**. The executing student account needs permission to read the notebook and utility file, use serverless compute, and read/write the managed volume and tables. The deployment identity needs permission to create a volume and tables in the configured schema (default: `workspace.default`).

The source notebook is maintained in `databricks-etl-pipeline/src/notebooks/`. Its cells use `spark.sql` and temporary views for the transformations, then check the resulting tables and Parquet output inside Databricks. The adjacent `utils.py` provides parameter setup and `write_data(frame, target, format="delta")` for managed tables; use `format="parquet"` for reporting exports. Deployment uploads this as a regular Python file beside the notebook so `from utils import setup_parameters, write_data` works. See [Databricks module imports](https://learn.microsoft.com/en-us/azure/databricks/files/workspace-modules).

To start the master ADF pipeline (the sales child runs its serverless Databricks job, then the dummy child runs on success):

```bash
uv run solution run-adf
```

Monitor execution in ADF Studio or inspect the returned run ID:

```bash
uv run solution status YOUR_RUN_ID
```

Run interactive notebook sessions and ADF executions sequentially because they write the same demo datasets. Stopping the local monitoring command does not cancel a remote run; inspect or cancel it in the workspace or ADF Studio.

### 5. Format and check deployment code

```bash
uv run prek install
uv run prek run --all-files
uv run pytest
```

Prek runs Ruff lint fixes and then `ruff format`, using the root `pyproject.toml`. For newly created, untracked files, use `uv run prek run --files path/to/file.py`. The small provisioning tests do not start Spark or contact Azure; students validate transformations in the Databricks notebook.

### 6. Clean up Azure resources

Use the exact `resource_group` from `config.py`:

```bash
uv run solution cleanup --confirm-resource-group YOUR_RESOURCE_GROUP
```

Cleanup verifies the group against Terraform state before destroying its managed resources, including stored demo data.

### Free Edition data flow

Deployment uploads the ten-row fixture to Azure, then stages a snapshot in a Databricks managed volume. ADF runs reuse that snapshot. Redeploy to refresh the course data. Bronze/Silver/Gold are managed Delta tables; the Azure `lakehouse` container is retained but unused by this workflow.

Manual notebook execution writes Parquet into the volume. Run `uv run solution run-adf` to also copy the report to Azure. The single-file export is intended for the ten-row example. Azure cleanup leaves Databricks jobs, notebooks, managed tables, and volumes; remove these separately in the workspace and Catalog Explorer.
