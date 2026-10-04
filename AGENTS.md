# Course workflow

- Students execute and test PySpark notebooks online in the Databricks workspace.
- Keep teaching transformation code in `databricks-etl-pipeline/src/notebooks/`.
- Do not add local Spark runners, Java setup, local ETL test suites, or separate saved-job runners unless explicitly requested.
- Keep `src/etl` focused on notebooks. Put instructor provisioning/upload helpers in `azure-terraform-provisioner/src/provisioner/`.
- Retain Terraform, automated through Python and one root `.env`; students should not need to edit Terraform.
- ADF is created with Python: one native Databricks Notebook activity pipeline, plus one dummy pipeline demonstrating Execute Pipeline dependencies.
- Keep tests small and beside deployment components, not at the repository root.
- Use root `prek.toml` and root `pyproject.toml` for Ruff linting and formatting.

- Keep each complete ADF pipeline in its own Python file under `azure-data-factory-pipeline/src/adf/defs/`.
- Register new ADF definitions only by importing the module and adding it to `PIPELINES` in `defs/__init__.py`; keep pipeline-building logic in `adf/deploy.py`.
