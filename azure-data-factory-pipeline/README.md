# Simple ADF pipelines

**Notebook path in, native serverless Job activity out. Deployment handles job IDs.**

Create one `src/adf/defs/pl_example.py`:

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

From the repository root:

```bash
uv run solution deploy --with-pipelines
uv run solution run-adf pl_example
```

No job IDs, separate job declarations, registry edits or Terraform changes. Paths are relative to `databricks-etl-pipeline/src/notebooks/`, without `.py`. Deployment validates them, uploads notebooks, creates/reuses one serverless job per notebook, then connects each native ADF Job activity to its job.

Each activity is a variable. `after=staging` waits for staging to succeed; `after=[country, demographic]` waits for both. The `activities` list includes the variables; list order alone does not set dependencies. Different parameters can be passed with `parameters={"year": "2021"}` and read through `dbutils.widgets.get("year")`. Deployment owns these jobs; keep notebook parameters in the definition rather than editing generated jobs in Studio. Runs sharing a notebook job queue when it is busy.

## ADF Studio is optional too

Prefer the UI? Run `solution deploy` without `--with-pipelines`. It provisions `ls_azure_databricks_serverless` (PAT) and `ls_azure_storage`, plus uploads notebooks. It does not touch jobs or pipelines.

Then add **Databricks Job** in ADF Studio, select the linked service, create/select a serverless job and its notebook tasks, and publish. Trigger manually or add a schedule. Serverless uses **Job**, not **Notebook**, activity. No Databricks Web activities are used.

## Helpers

| Helper | Purpose |
|---|---|
| `run_databricks_job(settings, name=..., notebook_path=..., parameters=..., after=...)` | Native serverless Job activity; IDs resolved automatically |
| `execute_pipeline(name=..., pipeline=..., parameters=..., after=...)` | Run a child pipeline and wait |
| `copy_file(name=..., source=..., destination=..., after=...)` | HTTP-to-Blob binary copy between existing datasets |

Each helper returns one activity. Parent pipelines declare `PIPELINE_DEPENDENCIES` so children deploy first. The included master runs sales, then demo on success; WHO is a separate four-step pipeline.

`--with-pipelines` updates matching pipeline definitions and repository-owned jobs. Plain `deploy` preserves Studio edits. Removing files does not delete deployed objects. Legacy Free Edition Web pipelines/linked services remain until removed explicitly.

Monitor runs in **ADF Monitor** and follow the Databricks run link for notebook/Spark details.
