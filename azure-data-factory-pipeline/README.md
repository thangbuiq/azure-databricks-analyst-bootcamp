# Add an ADF pipeline

Each file in `src/adf/defs/` defines **one complete pipeline**: its activities, parameters, and dependencies. Shared Databricks connection settings live in `src/adf/connections.py`.

The entry point is `pl_master_etl`. It waits for `pl_sales_pipeline` to execute the Databricks notebook successfully, then calls `pl_demo_pipeline`, a one-second dummy activity students can replace.

```text
pl_master_etl
  ├─ pl_sales_pipeline → serverless Databricks job
  └─ pl_demo_pipeline  → dummy wait (after sales succeeds)
```

## 1. Create a definition

Create `src/adf/defs/pl_example.py`:

```python
from azure.mgmt.datafactory import models as m

NAME = "pl_example"


def build_pipeline(settings) -> m.PipelineResource:
    return m.PipelineResource(
        description="A small example to demonstrate pipeline registration.",
        concurrency=1,
        activities=[
            m.WaitActivity(name="example_step", wait_time_in_seconds=1),
        ],
    )
```

Every definition exports:

- `NAME`: a unique ADF pipeline name.
- `build_pipeline(settings)`: returns the complete Azure SDK `PipelineResource`. `settings` contains the root `.env` configuration; it can be unused for a simple example.

The sales definition triggers a Databricks Job deployed by the provisioner. For other job definitions, copy its DatabricksJobActivity pattern. For pipeline dependencies, follow `pl_master_etl.py`: call a child pipeline with `wait_on_completion=True`, then specify a `Succeeded` dependency for the next activity. Use `settings.notebook_workspace_path("your_notebook")` for the notebook activity path inside the configured folder.

## 2. Import and register it

In `src/adf/defs/__init__.py`, add **one import** and include the module in `PIPELINES`:

```python
from adf.defs import pl_demo_pipeline, pl_master_etl, pl_sales_pipeline
from adf.defs import pl_example  # New import

PIPELINES = (
    pl_sales_pipeline,
    pl_demo_pipeline,
    pl_example,  # New registration
    pl_master_etl,
)
```

That is the only registration needed. Keep `__init__.py` limited to imports and `PIPELINES`.

`src/adf/deploy.py` builds and deploys every registered definition. The command-line choices, run validation, and deployment summary also read this registry; no additional name lists need editing.

Order entries so child pipelines are deployed before pipelines that reference them. `uv run solution run-adf` defaults to `pl_master_etl`. Registration makes a pipeline deployable and runnable independently; to include it in the master flow, add an `ExecutePipelineActivity` to `pl_master_etl.py` with its success dependency.

## 3. Deploy and run

From the repository root, with Azure already provisioned and `.env` configured:

```bash
uv run solution deploy
uv run solution run-adf  # Run the master
uv run solution run-adf pl_example  # Run an individual pipeline
```

The first command uploads all course notebooks, utilities and data and creates or updates all registered ADF pipelines. The run commands execute a pipeline in Azure and wait for its result. You can also run it from ADF Studio.

For a new transformation notebook, add a Python notebook starting with `# Databricks notebook source` under `databricks-etl-pipeline/src/notebooks/`. The deploy command automatically uploads all Python notebooks and shared utilities into the `DATABRICKS_NOTEBOOK_PATH` folder using `DATABRICKS_TOKEN`. Subfolders are preserved and notebook filenames lose `.py`; for example, `finance/report.py` is referenced as `settings.notebook_workspace_path("finance/report")`. Keep imported utilities beside their notebooks. Students execute and validate Spark transformations online in Databricks.

Removing a module from `PIPELINES` stops future deployment of that definition; it does not delete a pipeline already deployed to Azure.

## Format

```bash
uv run prek run --files azure-data-factory-pipeline/src/adf/defs/pl_example.py azure-data-factory-pipeline/src/adf/defs/__init__.py
```

Check pipeline execution in ADF Studio. This component has no local test suite.
