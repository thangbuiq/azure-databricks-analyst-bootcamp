# Course workflow

- Students execute and test PySpark notebooks online in the Databricks workspace.
- Keep teaching transformation code in `databricks-etl-pipeline/src/notebooks/`.
- Do not add local Spark runners, Java setup, local ETL test suites, or separate saved-job runners unless explicitly requested.
- Keep `src/notebooks` focused on teaching notebooks and shared notebook utilities. Put instructor provisioning/upload helpers in `azure-terraform-provisioner/src/provisioner/`.
- Retain Terraform, automated through Python. Keep credentials and essential inputs in one root `.env`, and configuration defaults in `provisioner/config.py`; students should not need to edit Terraform.
- Deploy all Python notebooks and utilities from `src/notebooks/` together into the folder `DATABRICKS_NOTEBOOK_PATH`, using `DATABRICKS_TOKEN` for workspace authentication.
- ADF is created with Python: `pl_master_etl` calls `pl_sales_pipeline`, then `pl_demo_pipeline` on success. The sales pipeline starts and polls a Databricks serverless job using Web activities (Free Edition URLs are rejected by the Azure Databricks Job activity), then copies the volume report to Azure; the demo is a dummy child.
- Keep provisioning tests small and beside their component, not at the repository root. Do not add ADF tests.
- Use root `prek.toml` and root `pyproject.toml` for Ruff linting and formatting.

- Keep each complete ADF pipeline in its own Python file under `azure-data-factory-pipeline/src/adf/defs/`.
- Discover `pl_*.py` definitions automatically. Declare Databricks jobs beside their pipeline using `serverless_job` and notebook paths; keep pipeline-building logic in `adf/deploy.py`.
- Analysts add notebooks and one definition file only. Do not require job IDs in `.env`, manual Databricks job creation, registry edits, or provisioner changes for a new notebook pipeline.
- Declare parent pipeline dependencies with `PIPELINE_DEPENDENCIES` so deployment creates child pipelines first.
