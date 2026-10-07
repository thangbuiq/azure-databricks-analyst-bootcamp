# ADF execution, report export, and pipeline development

Each file in `src/adf/defs/` defines **one complete pipeline**: its activities, parameters, and dependencies. Shared Databricks connection settings live in `src/adf/connections.py`.

The entry point is `pl_master_etl`. It waits for `pl_sales_pipeline` to execute the Databricks notebook and copy its report successfully, then calls `pl_demo_pipeline`, a one-second dummy activity students can replace.

```text
pl_master_etl
  ├─ pl_sales_pipeline → serverless job via Jobs API → copy volume report to Azure
  └─ pl_demo_pipeline  → dummy wait (after sales succeeds)
```

## How the sales export works

The implementation is in [pl_sales_pipeline.py](src/adf/defs/pl_sales_pipeline.py); linked services and datasets are in [connections.py](src/adf/connections.py).

| Activity | What it does |
|---|---|
| `sales_start` | POSTs the deployed job ID to `/api/2.2/jobs/run-now`; the idempotency token combines the ADF run ID with a stable suffix for this job step. |
| `sales_wait` | Waits 30 seconds between Jobs API status requests; stops on `TERMINATED`, `SKIPPED`, or `INTERNAL_ERROR`, with a one-hour timeout. |
| `sales_check` | Requires `result_state` to equal `SUCCESS`; otherwise `sales_failed` fails the pipeline. |
| `copy_report_to_azure` | Downloads the volume report over HTTP and writes it to the Azure `reports` container. Runs only after the result check succeeds. |

The HTTP source dataset `ds_volume_report` uses this request with the default volume configuration:

```text
GET <DATABRICKS_HOST>/api/2.0/fs/files/Volumes/workspace/default/analytics_demo/reports/sales/report.parquet
Authorization: Bearer <DATABRICKS_TOKEN>
```

The source linked service `ls_databricks_files` declares `Anonymous` authentication because it supplies authentication through an explicit secure `Authorization` header. The Databricks request itself is authenticated.

The destination dataset `ds_azure_report` writes to:

```text
https://<STORAGE_ACCOUNT>.blob.core.windows.net/reports/sales/report.parquet
```

The destination linked service `ls_report_storage` uses the storage account key obtained from Terraform outputs at deployment. Both datasets are `BinaryDataset`: ADF copies the existing Parquet bytes without parsing, aggregating, or converting them. The stable destination is replaced on subsequent successful copies. Only the report is transferred; Bronze/Silver/Gold Delta tables and transaction logs are not copied to Azure.

The job token must have access to run the job and read the volume report. The notebook's execution identity must be able to read the source volume and write the tables and report. Updating the root `.env` does not update deployed ADF credentials until `uv run solution deploy` runs again.

### Missing job IDs and retries

`INVALID_PARAMETER_VALUE: Job ... does not exist` means the ID sent to the selected workspace is unavailable. Job IDs belong to a workspace; deleting and recreating a job changes its ID. Check that ADF's Web activity URL matches `DATABRICKS_HOST` and that its body uses the current `course-sales-etl` job ID. An unpublished ADF Studio edit or an older deployed pipeline can still contain a stale ID.

Run `uv run solution deploy` to create or update the course job and deploy its returned ID into ADF together. The output's `databricks_jobs` mapping contains the current ID under `course-sales-etl`. Start a new ADF run after deployment. Do not retry an old run with stale inputs or add a manually maintained job ID to `.env`. Deployment also refreshes the source fixture, so account for that if you have edited the staged data.

Retry defaults live in [config.py](../azure-terraform-provisioner/src/provisioner/config.py):

| Layer | Policy | Purpose |
|---|---|---|
| ADF start and status Web activities | Three retries, 30 seconds apart | Retry failed API requests. These do not rerun a failed notebook. |
| Databricks notebook tasks | Two retries, minimum retry interval 60 seconds; retry timeouts enabled | Rerun an unsuccessful notebook attempt within the same job run. Each attempt has a 15-minute timeout. |
| Databricks job | 55-minute overall timeout | Bound execution, including retries, within ADF's one-hour polling window. |

The start request combines `pipeline().RunId` with a stable suffix derived from the helper’s `name`, so retries do not launch duplicate runs and different job steps in one pipeline have different tokens. See [Databricks run-now semantics](https://docs.databricks.com/api/jobs/v2/run-now) and [ADF activity retry policies](https://learn.microsoft.com/en-us/azure/data-factory/concepts-pipelines-activities). The task retry interval is measured from the failed attempt's start, so it is not necessarily a full minute after failure.

Retries are bounded, not restricted to transient error codes: ADF can also repeat a bad-ID or authentication request, and Databricks can retry a notebook assertion failure. They cannot repair invalid configuration or data. The overwrite-based teaching notebook supports reruns; review side effects before applying this retry policy to other notebooks. `WAITING_FOR_RETRY` is not terminal, so ADF continues polling until the job finishes and only copies after `SUCCESS`. If ADF monitoring times out, check the remote job separately; stopping monitoring does not cancel it.

## Run and verify the export

From the repository root, after provisioning and deployment:

```bash
uv run solution run-adf
uv run solution status YOUR_RUN_ID
```

`run-adf` prints the master run ID and waits for its result. To execute only the sales child, use `uv run solution run-adf pl_sales_pipeline`.

1. Open ADF Studio → **Monitor** → **Pipeline runs** and locate the run ID.
2. Follow the `run_sales` child execution to `pl_sales_pipeline`. Check the Databricks job result and `copy_report_to_azure` activity separately.
3. Open Azure Portal → your storage account → **Containers** → `reports` → `sales`. Confirm `report.parquet` exists and check its last-modified time and nonzero size.
4. Load the file using the [Power BI guide](../powerbi-business-report/README.md). Confirm two rows, 55 units, 550.00 revenue, and a sum of 10 for `sale_count`.

The master starts `pl_demo_pipeline` only after the sales child succeeds. The demo is a one-second wait. No scheduled ADF trigger or Power BI refresh activity is created by this repository.

## Troubleshoot the transfer

| Symptom | What to inspect |
|---|---|
| Notebook succeeds but Azure has no report | Manual notebook execution only writes the volume. Run the sales or master ADF pipeline. |
| `sales_start` returns 401/403 | Workspace host, token validity, and job permissions. Rotate the token in `.env` and redeploy if needed. |
| `sales_start` says the job does not exist | Verify the workspace and current job ID, then redeploy and start a new ADF run. See [missing job IDs and retries](#missing-job-ids-and-retries). |
| Job fails or polling times out | Open the Databricks job run and inspect the failing cell, serverless availability, and table/volume permissions. Copy does not run after a failed result check. |
| Copy source returns 401/403 | Files API token access to the report volume; this is separate from permission to start a job. |
| Copy source returns 404 | Confirm `report_path` from notebook parameters and the source dataset URL match, and that the notebook produced the file. |
| Copy sink returns 403 | Storage key validity, Shared Key authorization, and storage network restrictions. Redeploy to pick up a rotated key. |
| Azure `lakehouse` is empty | Expected: the destination is `reports/sales/report.parquet`. |
| Report contains old data | Check both the staged CSV and the last successful copy. Redeployment refreshes the snapshot from the repository fixture. |
| Power BI shows old totals after a successful copy | Refresh the Power BI semantic model separately. ADF does not trigger it. |

A previous report can remain after a later run fails. File existence alone is not proof of a successful current run; check the copy status and last-modified time. Avoid simultaneous manual notebook runs and ADF runs because they share table and file paths.

## Reuse activity helpers

[activities.py](src/adf/activities.py) keeps the Azure SDK details out of pipeline definitions:

| Helper | Purpose |
|---|---|
| `run_databricks_job(settings, name=..., job_id=..., after=...)` | Start an existing serverless job, poll, and require success. Returns three activities; use `*` inside the activity list. |
| `copy_file(name=..., source=..., destination=..., after=...)` | Copy bytes from an HTTP source dataset to an Azure Blob destination dataset. |
| `execute_pipeline(name=..., pipeline=..., after=...)` | Run a child pipeline and wait for completion. |

`after` is optional and names one activity that must succeed first. Give every helper call a unique `name`. A Databricks call named `sales` creates `sales_start`, `sales_wait`, and `sales_check`; subsequent steps should depend on **`sales_check`**, which confirms the job succeeded.

For example, the sales pipeline defines its activities as:

```python
activities = [
    *run_databricks_job(settings, name="sales", job_id=job_ids[DATABRICKS_JOBS[0].name]),
    copy_file(
        name="copy_report_to_azure",
        source=VOLUME_REPORT,
        destination=AZURE_REPORT,
        after="sales_check",
    ),
]
```

Import the helpers from `adf.activities` and dataset constants from `adf.connections`. The complete working definition is [pl_sales_pipeline.py](src/adf/defs/pl_sales_pipeline.py).

A second job can use `after="sales_check"` to run after the first. Each job call has distinct activity names and retry tokens. Declared jobs are created or updated automatically on Serverless compute.

`copy_file` takes **dataset names**, not paths. Register new datasets and linked services in `connections.py`; the helper does not create them. It transfers an existing file unchanged, not a Delta table or a query result.

## Add a notebook pipeline

Add notebooks below `../databricks-etl-pipeline/src/notebooks/`, then create one `pl_*.py` file in `src/adf/defs/`. For example:

```python
from azure.mgmt.datafactory import models as m

from adf.activities import run_databricks_job
from adf.jobs import serverless_job

NAME = "pl_example"
DATABRICKS_JOBS = (
    serverless_job(
        "course-example-etl",
        notebooks=("example/01_staging", "example/02_transform"),
    ),
)


def build_pipeline(settings, job_ids) -> m.PipelineResource:
    return m.PipelineResource(
        description="Run the example notebooks in order.",
        concurrency=1,
        activities=[
            *run_databricks_job(
                settings,
                name="example",
                job_id=job_ids[DATABRICKS_JOBS[0].name],
            ),
        ],
    )
```

That file is the complete registration. Deployment scans `pl_*.py` definitions automatically. Every definition exports:

- `NAME`: a unique ADF pipeline name.
- `DATABRICKS_JOBS`: optional serverless job declarations. Plain notebook paths run sequentially.
- `build_pipeline(settings, job_ids)`: returns the complete Azure SDK `PipelineResource`; `job_ids` contains generated IDs keyed by declared job name.

Notebook paths are relative to `DATABRICKS_NOTEBOOK_PATH` and omit `.py`. Deployment rejects missing, absolute, parent-relative, or `.py` paths before cloud writes. Use `notebook_task(...)` from `adf.jobs` only when a job needs a custom dependency graph.

For a parent ADF pipeline, declare child names and use `execute_pipeline`:

```python
PIPELINE_DEPENDENCIES = ("pl_example",)
```

Discovery deploys children before parents and rejects missing or cyclic dependencies.

## Deploy and run

From the repository root, with Azure already provisioned and `.env` configured:

```bash
uv run solution deploy
uv run solution run-adf  # Run the master
uv run solution run-adf pl_example  # Run an individual pipeline
```

The first command uploads every notebook and utility, creates or resets every declared Databricks job, and deploys every discovered ADF pipeline. Generated job IDs remain deployment output; do not add them to `.env`.

Removing a definition stops future updates; it does not delete an existing ADF pipeline or Databricks job.

## Format

```bash
uv run prek run --files azure-data-factory-pipeline/src/adf/defs/pl_example.py
```

Check pipeline execution in ADF Studio. This component has no local test suite.
