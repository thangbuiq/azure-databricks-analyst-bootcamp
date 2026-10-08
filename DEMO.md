# WHO suicide rates demo

**Azure CSV → four PySpark notebooks → star schema in `bnstprod.dm_who` → Power BI.**

Source: [Kaggle dataset](https://www.kaggle.com/datasets/samartalwar/global-suicide-rates-and-socioeconomic-indicators). The repository CSV contains 18,315 rows across 185 countries, 2000–2021.

## 1. Storage and deployment

Set root `.env` for your Azure Databricks workspace, token, storage account and existing Unity Catalog catalog, then run:

```bash
uv run solution setup
```

Deployment configures an Access Connector, Unity Catalog external locations and `dm_who`. Keep the source CSV in Azure at:

```text
abfss://raw@<STORAGE_ACCOUNT>.dfs.core.windows.net/who/global_suicide_rates_real_who_worldbank.csv
```

The existing Blob URL and this `abfss` URL address the same file when the account matches. No upload to Databricks is needed. Delta data is written to `lakehouse/dm_who/<table>` in that storage account.

## 2. Four notebooks

Files are in **`databricks-etl-pipeline/src/notebooks/who/`**. Each code block below is a separate Databricks code cell; the headings are Markdown cells.

Paths and tables are hard-coded for `bdastorageaccountmaster` and `bnstprod.dm_who`. Edit the values directly when using another account or catalog. Deployment uploads the files unchanged.

| Notebook | Output table | Grain |
|---|---|---|
| `01_staging.py` | `stg_suicide` | Cleaned source observation |
| `02_dim_country_year.py` | `dim_country_year` | Country + year |
| `03_dim_demographic.py` | `dim_demographic` | Sex + age bracket + generation |
| `04_fact_suicide_rate.py` | `fact_suicide_rate` | Country-year + demographic |

### `01_staging.py`

#### 1. Locations
Edit these values directly if your account or table changes.

```python
target_table = "bnstprod.dm_who.stg_suicide"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/stg_suicide"
source_path = "abfss://raw@bdastorageaccountmaster.dfs.core.windows.net/who/global_suicide_rates_real_who_worldbank.csv"
```

#### 2. Read the CSV

```python
raw = spark.read.option("header", True).option("mode", "FAILFAST").csv(source_path)
raw.createOrReplaceTempView("raw_who")
```

#### 3. Transform

```python
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
```

#### 4. Write the Delta table

```python
print(f"Writing {target_table} to {target_path}")
(df.write.format("delta").mode("overwrite").option("path", target_path).saveAsTable(target_table))
print(f"Written: {target_table}")
```

#### 5. Optimize the Delta files

```python
spark.sql(f"OPTIMIZE {target_table}")
print(f"Optimized: {target_table} at {target_path}")
```

### `02_dim_country_year.py`

#### 1. Locations
Edit these values directly if your account or table changes.

```python
target_table = "bnstprod.dm_who.dim_country_year"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/dim_country_year"
```

#### 2. Transform

```python
df = spark.sql("""
    SELECT DISTINCT
        CONCAT(country_code, '_', CAST(year AS STRING)) AS country_year_key,
        country_code, country_name, year,
        gdp_usd, gdp_per_capita_usd, total_country_population
    FROM bnstprod.dm_who.stg_suicide
""")
```

#### 3. Write the Delta table

```python
print(f"Writing {target_table} to {target_path}")
(df.write.format("delta").mode("overwrite").option("path", target_path).saveAsTable(target_table))
print(f"Written: {target_table}")
```

#### 4. Optimize the Delta files

```python
spark.sql(f"OPTIMIZE {target_table}")
print(f"Optimized: {target_table} at {target_path}")
```

### `03_dim_demographic.py`

#### 1. Locations
Edit these values directly if your account or table changes.

```python
target_table = "bnstprod.dm_who.dim_demographic"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/dim_demographic"
```

#### 2. Transform

```python
df = spark.sql("""
    SELECT DISTINCT
        SHA2(TO_JSON(NAMED_STRUCT(
            'sex', sex, 'age_bracket', age_bracket, 'generation', generation
        )), 256) AS demographic_key,
        sex, age_bracket, generation
    FROM bnstprod.dm_who.stg_suicide
""")
```

#### 3. Write the Delta table

```python
print(f"Writing {target_table} to {target_path}")
(df.write.format("delta").mode("overwrite").option("path", target_path).saveAsTable(target_table))
print(f"Written: {target_table}")
```

#### 4. Optimize the Delta files

```python
spark.sql(f"OPTIMIZE {target_table}")
print(f"Optimized: {target_table} at {target_path}")
```

### `04_fact_suicide_rate.py`

#### 1. Locations
Edit these values directly if your account or table changes.

```python
target_table = "bnstprod.dm_who.fact_suicide_rate"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/fact_suicide_rate"
```

#### 2. Transform

```python
df = spark.sql("""
    SELECT c.country_year_key, d.demographic_key, s.suicide_rate_per_100k
    FROM bnstprod.dm_who.stg_suicide s
    JOIN bnstprod.dm_who.dim_country_year c
      ON s.country_code = c.country_code AND s.year = c.year
    JOIN bnstprod.dm_who.dim_demographic d
      ON s.sex = d.sex AND s.age_bracket = d.age_bracket AND s.generation = d.generation
""")
```

#### 3. Write the Delta table

```python
print(f"Writing {target_table} to {target_path}")
(df.write.format("delta").mode("overwrite").option("path", target_path).saveAsTable(target_table))
print(f"Written: {target_table}")
```

#### 4. Optimize the Delta files

```python
spark.sql(f"OPTIMIZE {target_table}")
print(f"Optimized: {target_table} at {target_path}")
```

## 3. Run the WHO notebooks with ADF Studio

The root [README](README.md) has the end-to-end ADF Studio steps and screenshots. Create a Databricks linked service that uses an all-purpose cluster, then add four Databricks Notebook activities with these workspace paths:

| Activity | Notebook path |
|---|---|
| `stg_suicide` | `/Shared/analytics-demo/who/01_staging` |
| `dim_country_year` | `/Shared/analytics-demo/who/02_dim_country_year` |
| `dim_demographic` | `/Shared/analytics-demo/who/03_dim_demographic` |
| `fact_suicide_rate` | `/Shared/analytics-demo/who/04_fact_suicide_rate` |

Connect staging to both dimension activities, then connect both dimensions to the fact activity. Validate and debug the pipeline, publish it after a successful run, and check **Monitor** for activity results.

## 4. Power BI report examples — reference only

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
