# Add an ADF pipeline

Each file in `src/adf/defs/` defines **one complete pipeline**: its activities, parameters, and dependencies. Shared Databricks connection settings live in `src/adf/connections.py`.

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

For notebook execution, copy the notebook activity pattern from `pl_sales_job.py`. For pipeline dependencies, follow `pl_dependency_demo.py`: call a child pipeline with `wait_on_completion=True`, then specify a `Succeeded` dependency for the next activity. The target notebook must already exist in the Databricks workspace.

## 2. Import and register it

In `src/adf/defs/__init__.py`, add **one import** and include the module in `PIPELINES`:

```python
from adf.defs import pl_dependency_demo, pl_sales_job
from adf.defs import pl_example  # New import

PIPELINES = (
    pl_sales_job,
    pl_dependency_demo,
    pl_example,  # New registration
)
```

That is the only registration needed. Keep `__init__.py` limited to imports and `PIPELINES`.

`src/adf/deploy.py` builds and deploys every registered definition. The command-line choices, run validation, and deployment summary also read this registry; no additional name lists need editing.

Order entries so child pipelines are deployed before pipelines that reference them. The first entry is the default for `uv run solution run-adf`.

## 3. Deploy and run

From the repository root, with Azure already provisioned and `.env` configured:

```bash
uv run solution deploy
uv run solution run-adf pl_example
```

The first command uploads the course notebook/data and creates or updates all registered ADF pipelines. The second executes the selected pipeline in Azure and waits for its result. You can also run it from ADF Studio.

For a new transformation notebook, add it under `databricks-etl-pipeline/src/notebooks/`, upload it to the Databricks workspace, and point the new Notebook activity at its workspace path. Registering an ADF definition does not automatically upload additional notebooks; the setup helper uploads the existing course notebook. Students execute and validate Spark transformations online in Databricks.

Removing a module from `PIPELINES` stops future deployment of that definition; it does not delete a pipeline already deployed to Azure.

## Format and check

```bash
uv run prek run --files azure-data-factory-pipeline/src/adf/defs/pl_example.py azure-data-factory-pipeline/src/adf/defs/__init__.py
uv run pytest azure-data-factory-pipeline/tests
```
