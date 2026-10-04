# azure-databricks-analyst-bootcamp

> A hands-on Medallion-architecture bootcamp repo that takes Data Analysts from raw Azure Blob data to Power BI dashboards, using Databricks Spark, Delta Lake, and Azure Data Factory.

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
| `databricks-etl-pipeline/` | Dummy source data and PySpark transformation notebooks under `src/notebooks/` |
| `powerbi-business-report/` | Power BI reporting layer consuming the exported Parquet data |

See [adding pipeline definitions](azure-data-factory-pipeline/README.md) for the import-and-register workflow.

---

## Orchestration Flow

```mermaid
sequenceDiagram
    participant Parent as Parent ADF Pipeline
    participant Child as Notebook ADF Pipeline
    participant Notebook as Databricks Notebook
    participant Blob as Azure Blob Storage
    participant PBI as Power BI

    Parent->>Child: Execute Pipeline and wait for completion
    Child->>Notebook: Execute notebook by workspace path
    Notebook->>Blob: Read raw data
    Note over Notebook: Bronze → Silver → Gold using Spark and Delta Lake
    Notebook->>Blob: Export Gold as Parquet
    Notebook-->>Child: Execution result
    Child-->>Parent: Continue dependent activity on success
    Note over PBI: Refresh reads the exported Parquet data
```

---

## Tech Stack

| Concern | Technology |
|---|---|
| Infrastructure | Azure resources provisioned with Terraform through Python |
| Source storage | Azure Blob Storage / ADLS Gen2 |
| Compute / transform | Azure Databricks (PySpark notebooks) |
| Storage format | Delta Lake (Bronze/Silver/Gold) |
| Orchestration | Azure Data Factory, configured with Python |
| BI export format | Parquet (Blob Storage) |
| BI / reporting | Power BI |
| Configuration | One root `.env` file |
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

Use [.env.example](.env.example) as the configuration reference. Fill in these required values:

| Variable | Description |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_TENANT_ID` | Microsoft Entra tenant ID |
| `AZURE_CLIENT_ID` | Deployment service principal's application/client ID |
| `AZURE_CLIENT_SECRET` | Deployment service principal's secret |
| `AZURE_PRINCIPAL_OBJECT_ID` | Service principal object ID from Enterprise Applications, not the application registration object ID |
| `STORAGE_ACCOUNT` | Globally unique storage account name: 3-24 lowercase letters/numbers |

Review the region and resource names in `.env`. Choose a dedicated resource group and a globally unique Data Factory name. Databricks runtime, node type, notebook workspace path, secret scope, and execution timeout are also configurable there. No Terraform files or separate variable files need editing.

The instructor prepares an identity with permission to create Azure resources and role assignments, such as **Contributor + User Access Administrator** in the training subscription, and to register resource providers when necessary. It also needs Databricks workspace administration permissions for notebook upload, secrets, and managed-identity setup.

If the Databricks account restricts workspace-level identity creation, set `DATABRICKS_ACCOUNT_ID` with an authorized account-admin identity, or ask the administrator to assign the ADF identity to the workspace. If using `DATABRICKS_POLICY_ID`, allow the ADF identity to use that compute policy.

Keep `.env` private. It is Git-ignored. Authentication secrets are stored in a Databricks secret scope, not embedded in the notebook.

### 3. Provision and deploy

```bash
uv run solution setup
```

This command automatically runs Terraform, provisions the Azure resources, uploads the ten-row source CSV and notebook, and creates the ADF connections and pipeline definitions. The uploaded notebook receives non-secret widget defaults from `.env` so it can also run interactively in the workspace.

**Setup creates billable Azure resources and applies infrastructure changes automatically.** Keep the Terraform state files in `azure-terraform-provisioner/`; they are required to update and clean up the same deployment. Do not reuse that state with another deployment's configuration.

To update the notebook, data, and ADF definitions after provisioning:

```bash
uv run solution deploy
```

### 4. Execute online

Open the Databricks workspace and navigate to the notebook path configured in `.env`. Attach suitable **dedicated compute** and select **Run All**. The executing student account needs permission to run the notebook, use compute, and read the configured secret scope; the instructor grants these permissions once.

The source notebook is maintained in `databricks-etl-pipeline/src/notebooks/`. It executes the transformations and checks the resulting tables and Parquet output inside Databricks.

To start the default ADF execution from your local machine:

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

Prek runs Ruff lint fixes and then `ruff format`, using the root `pyproject.toml`. For newly created, untracked files, use `uv run prek run --files path/to/file.py`. The small deployment tests do not start Spark or contact Azure; students validate transformations in the Databricks notebook.

### 6. Clean up Azure resources

Use the exact resource group from `.env`:

```bash
uv run solution cleanup --confirm-resource-group YOUR_RESOURCE_GROUP
```

Cleanup verifies the group against Terraform state before destroying its managed resources, including stored demo data. Any Databricks account-level identity registration may require separate administrator cleanup if no longer used.
