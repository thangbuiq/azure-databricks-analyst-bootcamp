# WHO suicide rates demo

**Azure CSV → four PySpark notebooks → star schema in `workspace.dm_who` → Power BI.**

> Need an example implementation? See the [`reference/solution` branch](../../tree/reference/solution) for the completed notebooks and optional ADF pipeline.

## 1. Prepare storage

Set the required Azure Databricks workspace, token, storage account and Unity Catalog catalog values in the root `.env`, then run:

```bash
uv run solution setup
```

Keep the source CSV in Azure at:

```text
abfss://raw@<STORAGE_ACCOUNT>.dfs.core.windows.net/who/global_suicide_rates_real_who_worldbank.csv
```

Delta tables are stored under `lakehouse/dm_who/<table>` in that storage account.

## 2. Build and deploy the notebooks

Create four notebooks in `databricks-etl-pipeline/src/notebooks/who/`, then deploy them with:

```bash
uv run solution deploy
```

| Notebook | Output table | Grain |
|---|---|---|
| `01_staging.py` | `stg_suicide` | Cleaned source observation |
| `02_dim_country_year.py` | `dim_country_year` | Country + year |
| `03_dim_demographic.py` | `dim_demographic` | Sex + age bracket + generation |
| `04_fact_suicide_rate.py` | `fact_suicide_rate` | Country-year + demographic |

Keep notebook paths hard-coded. Use separate Markdown and code cells, print each Delta write destination, and run `OPTIMIZE` after every write. Build both dimensions after staging; build the fact table after both dimensions.

## 3. Run the optional ADF pipeline

Use ADF Studio or deploy and run the Python definition:

```bash
uv run solution deploy --with-pipelines
uv run solution run-adf pl_who_pipeline
```

## 4. Explore in Power BI

Connect Power BI to the Unity Catalog tables in `workspace.dm_who`. Relate `fact_suicide_rate` to `dim_country_year` and `dim_demographic` using their keys, then explore rates by country, year and demographic group.
