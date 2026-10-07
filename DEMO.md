# WHO suicide rates demo

**Azure CSV → four PySpark notebooks → star schema in `workspace.dm_who` → Power BI.**

Source: [Kaggle dataset](https://www.kaggle.com/datasets/samartalwar/global-suicide-rates-and-socioeconomic-indicators). The repository CSV contains 18,315 rows across 185 countries, 2000–2021.

## 1. Prepare the data

Run in a Databricks SQL cell:

```sql
CREATE SCHEMA IF NOT EXISTS workspace.dm_who;
CREATE VOLUME IF NOT EXISTS workspace.dm_who.analytics_demo;
```

Download the `global_suicide_rates_real_who_worldbank.csv`. Upload it in Databricks Catalog Explorer to **workspace → dm_who → analytics_demo → raw/who**:

```text
/Volumes/workspace/dm_who/analytics_demo/raw/who/global_suicide_rates_real_who_worldbank.csv
```

Alternatively, upload `data/global_suicide_rates_real_who_worldbank.csv` from this repository. This is a snapshot: upload again when the Azure CSV changes.

## 2. Create four notebooks

Create these files in **`databricks-etl-pipeline/src/notebooks/who/`**. Each writes exactly one table. Use these four files instead of the earlier eight-file layout.

| File | Table in `workspace.dm_who` | Grain | Rows |
|---|---|---|---:|
| `01_staging.py` | `stg_suicide` | Source observation, cleaned and typed | 18,315 |
| `02_dim_country_year.py` | `dim_country_year` | Country + year, including GDP/population | 4,070 |
| `03_dim_demographic.py` | `dim_demographic` | Sex + age bracket + generation | 36 |
| `04_fact_suicide_rate.py` | `fact_suicide_rate` | Country-year + demographic | 18,315 |

```text
dim_country_year ── country_year_key ── fact_suicide_rate ── demographic_key ── dim_demographic
```

### `01_staging.py`

```python
# Databricks notebook source
raw = (
    spark.read.option("header", True)
    .option("inferSchema", False)
    .option("mode", "FAILFAST")
    .csv("/Volumes/workspace/dm_who/analytics_demo/raw/who/global_suicide_rates_real_who_worldbank.csv")
)
raw.createOrReplaceTempView("raw_who")

# COMMAND ----------
df = spark.sql("""
    SELECT
        TRIM(country) AS country_name,
        UPPER(TRIM(country_code)) AS country_code,
        CAST(year AS INT) AS year,
        LOWER(TRIM(sex)) AS sex,
        LOWER(TRIM(age_bracket)) AS age_bracket,
        TRIM(generation) AS generation,
        CAST(suicide_rate_per_100k AS DOUBLE) AS suicide_rate_per_100k,
        CAST(NULLIF(TRIM(gdp_usd), '') AS DOUBLE) AS gdp_usd,
        CAST(NULLIF(TRIM(gdp_per_capita_usd), '') AS DOUBLE) AS gdp_per_capita_usd,
        CAST(CAST(total_country_population AS DOUBLE) AS BIGINT) AS total_country_population
    FROM raw_who
""")

assert df.count() == 18315
assert df.select("country_code", "year", "sex", "age_bracket", "generation").distinct().count() == 18315
assert df.filter("country_code IS NULL OR year IS NULL OR suicide_rate_per_100k IS NULL").count() == 0
assert df.filter("suicide_rate_per_100k < 0 OR isnan(suicide_rate_per_100k)").count() == 0

df.write.mode("overwrite").saveAsTable("workspace.dm_who.stg_suicide")
display(df.limit(10))
```

### `02_dim_country_year.py`

GDP and population repeat across source demographics. Keep one copy per country-year.

```python
# Databricks notebook source
df = spark.sql("""
    SELECT DISTINCT
        CONCAT(country_code, '_', CAST(year AS STRING)) AS country_year_key,
        country_code, country_name, year,
        gdp_usd, gdp_per_capita_usd, total_country_population
    FROM workspace.dm_who.stg_suicide
""")

assert df.count() == 4070
assert df.select("country_year_key").distinct().count() == 4070
assert df.filter("gdp_usd IS NULL").count() == 50

df.write.mode("overwrite").saveAsTable("workspace.dm_who.dim_country_year")
display(df.limit(10))
```

### `03_dim_demographic.py`

```python
# Databricks notebook source
df = spark.sql("""
    SELECT DISTINCT
        SHA2(TO_JSON(NAMED_STRUCT(
            'sex', sex, 'age_bracket', age_bracket, 'generation', generation
        )), 256) AS demographic_key,
        sex, age_bracket, generation
    FROM workspace.dm_who.stg_suicide
""")

assert df.count() == 36
assert df.select("demographic_key").distinct().count() == 36

df.write.mode("overwrite").saveAsTable("workspace.dm_who.dim_demographic")
display(df)
```

### `04_fact_suicide_rate.py`

```python
# Databricks notebook source
df = spark.sql("""
    SELECT c.country_year_key, d.demographic_key, s.suicide_rate_per_100k
    FROM workspace.dm_who.stg_suicide s
    JOIN workspace.dm_who.dim_country_year c
      ON s.country_code = c.country_code AND s.year = c.year
    JOIN workspace.dm_who.dim_demographic d
      ON s.sex = d.sex AND s.age_bracket = d.age_bracket AND s.generation = d.generation
""")

assert df.count() == 18315
assert df.select("country_year_key", "demographic_key").distinct().count() == 18315

df.write.mode("overwrite").saveAsTable("workspace.dm_who.fact_suicide_rate")
display(df.limit(10))
```

## 3. Deploy and create the Databricks job

With the existing course resources and root `.env` configured, run from the repository root:

```bash
uv run solution deploy
```

This uploads all notebooks/utilities to `DATABRICKS_NOTEBOOK_PATH` using `DATABRICKS_TOKEN`, and refreshes the existing sales deployment. The WHO notebooks appear in its **who** subfolder.

In Databricks **Jobs & Pipelines**, create a job named **course-who-etl** with these Notebook tasks. Select **Serverless** for every task and **All succeeded** for dependent tasks:

| Task key | Notebook under `DATABRICKS_NOTEBOOK_PATH` | Depends on |
|---|---|---|
| `staging` | `who/01_staging` | — |
| `country_year` | `who/02_dim_country_year` | `staging` |
| `demographic` | `who/03_dim_demographic` | `country_year` |
| `fact` | `who/04_fact_suicide_rate` | `demographic` |

Set maximum concurrent runs to **1**. Run the job once, confirm all four tasks succeed, and copy its **Job ID**. Each task reads saved tables; it does not need variables from another notebook. See [Databricks task configuration](https://docs.databricks.com/aws/en/jobs/configure-task).

## 4. Add the ADF pipeline

```text
pl_who_pipeline
  → POST jobs/run-now
  → Until: wait 30 seconds → GET jobs/runs/get
  → Check result_state = SUCCESS; otherwise fail
```

Use the shared helpers in `adf/activities.py`. The Azure Databricks Job activity rejects the course Free Edition URL; [Web activities](https://learn.microsoft.com/en-us/azure/data-factory/control-flow-web-activity) call the Jobs API instead.

### A. Save the WHO job ID

Add to the existing root **`.env`**, replacing the example with your Job ID:

```dotenv
WHO_DATABRICKS_JOB_ID=123456789
```

In **`azure-terraform-provisioner/src/provisioner/config.py`**, add this field inside `Settings`, beside `databricks_job_id`:

```python
    who_databricks_job_id: str = ""
```

Inside `load_settings`, add this argument to the existing `s = Settings(...)` call:

```python
        who_databricks_job_id=get("WHO_DATABRICKS_JOB_ID"),
```

### B. Create the WHO definition

Create **`azure-data-factory-pipeline/src/adf/defs/pl_who_pipeline.py`**:

```python
from azure.mgmt.datafactory import models as m

from adf.activities import run_databricks_job

NAME = "pl_who_pipeline"


def build_pipeline(settings):
    return m.PipelineResource(
        description="Run the four WHO notebooks on Serverless.",
        concurrency=1,
        activities=[
            *run_databricks_job(settings, name="who", job_id=settings.who_databricks_job_id),
        ],
    )
```

The `*` inserts the helper's three activities: **who_start → who_wait → who_check**. It starts the existing job, polls every 30 seconds, and fails the pipeline if the job does not succeed. Use a unique `name` for each job call.

The sales pipeline also uses `copy_file(...)` from `adf.activities`; see [the complete example](azure-data-factory-pipeline/src/adf/defs/pl_sales_pipeline.py). It takes registered source/destination dataset names and `after="sales_check"`. WHO currently produces tables only; exporting a WHO file would also require an output file and its own datasets in `adf/connections.py`.

### C. Register the definition

Replace **`azure-data-factory-pipeline/src/adf/defs/__init__.py`** with:

```python
"""Register children before the master that calls them."""

from adf.defs import pl_demo_pipeline, pl_master_etl, pl_sales_pipeline, pl_who_pipeline

PIPELINES = (pl_sales_pipeline, pl_demo_pipeline, pl_who_pipeline, pl_master_etl)
```

The existing `adf/deploy.py` builds and deploys registered definitions. Keep `pl_master_etl` as sales → dummy demo; run the WHO pipeline separately.

### D. Deploy and run

```bash
uv run solution deploy
uv run solution run-adf pl_who_pipeline
```

In ADF Monitor, confirm **who_start → who_wait → who_check** succeed. Confirm the four WHO tables exist under **workspace → dm_who**. Reruns overwrite them. ADF uses the staged CSV; it does not refresh the Azure-to-volume snapshot.

## 5. Power BI report examples — reference only

Load the three final tables into Power BI using the Databricks connector and your workspace SQL warehouse connection details. Do not load `stg_suicide` into the report model.

Create **one-to-many**, single-direction relationships:

- `dim_country_year[country_year_key]` → `fact_suicide_rate[country_year_key]`
- `dim_demographic[demographic_key]` → `fact_suicide_rate[demographic_key]`

These are example questions for students' final reports, not another notebook or pipeline task:

| Question | Suggested visual | Filters / calculation |
|---|---|---|
| How have reported rates changed? | Line chart by year | `sex = both`, `age_bracket = all_ages`; average country rates |
| Which countries have the highest rates? | Top-10 country bar chart | Year 2021, both sexes, all ages |
| How do male and female rates differ? | Clustered bars by country | Year 2021, all ages; show male and female separately |
| How do rates vary by age? | Age-group bar chart | Year 2021, both sexes; use `10-19`, `20-29`, `30-39`, `40-49`, `50-59`, `60-69`, `70plus` |
| Is income associated with the rate? | Country scatter plot | Year 2021, both sexes, all ages; GDP per capita vs rate; exclude missing GDP |

Reference results from the repository CSV: the unweighted country mean is **10.3956** in 2000 and **8.5459** in 2021; Lesotho has the highest 2021 both-sex/all-age rate at **28.66**.

Rates are **not additive**. The country mean is not a global population rate. Age bands overlap outside the selected set; age-specific data exists only for 2021. Calculate GDP/population totals from `dim_country_year` for a single year, not from a join to demographic facts. Correlation does not establish causation.
