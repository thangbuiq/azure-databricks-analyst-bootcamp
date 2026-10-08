# Course workflow

- Students execute and test PySpark notebooks online in the Databricks workspace.
- Keep teaching transformation code in `databricks-etl-pipeline/src/notebooks/`.
- Do not add local Spark runners, Java setup, local ETL test suites, or separate saved-job runners unless explicitly requested.
- Keep `src/notebooks` focused on teaching notebooks and shared notebook utilities. Put instructor provisioning/upload helpers in `azure-terraform-provisioner/src/provisioner/`.
- Retain Terraform, automated through Python. Keep credentials and essential inputs in one root `.env`, and configuration defaults in `provisioner/config.py`; students should not need to edit Terraform.
- Deploy all Python notebooks and utilities from `src/notebooks/` together into the folder `DATABRICKS_NOTEBOOK_PATH`, using `DATABRICKS_TOKEN` for workspace authentication.
- Keep provisioning tests small and beside their component, not at the repository root. Do not add ADF tests.
- Use root `prek.toml` and root `pyproject.toml` for Ruff linting and formatting.

- Keep each complete ADF pipeline in its own Python file under `azure-data-factory-pipeline/src/adf/defs/`.
- Declare parent pipeline dependencies with `PIPELINE_DEPENDENCIES` so deployment creates child pipelines first.
- Default deployment provisions native Azure Databricks serverless PAT linked services and uploads notebooks, without creating jobs or ADF pipelines.
- Python pipeline definitions are optional and discovered only with --with-pipelines. Build functions accept settings; use native Databricks Job activities, never Databricks Web polling.
- Python definitions call run_databricks_job with a notebook_path. Deployment creates/reuses owned serverless jobs and injects IDs automatically; no separate job declarations or manual IDs. Studio-only users can create/select jobs there.
- Read Azure Storage directly through Unity Catalog external locations backed by an Access Connector. Write external Delta tables under the lakehouse container; do not stage data in workspace volumes.
- Keep notebook locations hard-coded and writes explicit. No widgets, assertions, setup_parameters/write_data wrappers, or top-level utils.py. Separate steps into Markdown/code cells, print write destinations, and run OPTIMIZE after every Delta write. Upload source unchanged and keep DEMO.md synchronized.
