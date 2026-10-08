# Course workflow

- Students execute and test PySpark notebooks online in the Databricks workspace.
- Keep teaching transformation code in `databricks-etl-pipeline/src/notebooks/`.
- Do not add local Spark runners, Java setup, local ETL test suites, or separate saved-job runners unless explicitly requested.
- Keep `src/notebooks` focused on teaching notebooks and shared notebook utilities. Put instructor provisioning/upload helpers in `azure-terraform-provisioner/src/provisioner/`.
- Retain Terraform, automated through Python. Keep credentials and essential inputs in one root `.env`, and configuration defaults in `provisioner/config.py`; students should not need to edit Terraform.
- Deploy all Python notebooks and utilities from `src/notebooks/` together into the folder `DATABRICKS_NOTEBOOK_PATH`, using `DATABRICKS_TOKEN` for workspace authentication.
- Keep provisioning tests small and beside their component, not at the repository root. Do not add ADF tests.
- Use root `prek.toml` and root `pyproject.toml` for Ruff linting and formatting.

- Keep the Azure Data Factory resource in Terraform. Students create Databricks linked services and pipelines in ADF Studio; do not add Python ADF pipeline definitions or pipeline runners.
- Provisioning configures Unity Catalog storage access and uploads notebooks, without creating ADF linked services, Databricks jobs, or ADF pipelines.
- Read Azure Storage directly through Unity Catalog external locations backed by an Access Connector. Write external Delta tables under the lakehouse container; do not stage data in workspace volumes.
- Keep notebook locations hard-coded and writes explicit. No widgets, assertions, setup_parameters/write_data wrappers, or top-level utils.py. Separate steps into Markdown/code cells, print write destinations, and run OPTIMIZE after every Delta write. Upload source unchanged and keep DEMO.md synchronized.
