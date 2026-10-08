"""Four notebooks, one table each; ADF controls the execution order."""

from azure.mgmt.datafactory import models as m

from adf.activities import run_databricks_job

NAME = "pl_who_pipeline"


def build_pipeline(settings):
    staging = run_databricks_job(settings, name="staging", notebook_path="who/01_staging")
    country = run_databricks_job(settings, name="country", notebook_path="who/02_dim_country_year", after=staging)
    demographic = run_databricks_job(
        settings, name="demographic", notebook_path="who/03_dim_demographic", after=staging
    )
    fact = run_databricks_job(
        settings, name="fact", notebook_path="who/04_fact_suicide_rate", after=[country, demographic]
    )

    return m.PipelineResource(concurrency=1, activities=[staging, country, demographic, fact])
