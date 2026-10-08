# Databricks notebook source

# MAGIC %md
# MAGIC # WHO — stg_suicide
# MAGIC Read Azure data and write one Delta table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Locations
# MAGIC Edit these values directly if your account or table changes.

# COMMAND ----------

target_table = "bnstprod.dm_who.stg_suicide"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/stg_suicide"
source_path = "abfss://raw@bdastorageaccountmaster.dfs.core.windows.net/who/global_suicide_rates_real_who_worldbank.csv"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Read the CSV

# COMMAND ----------

raw = spark.read.option("header", True).option("mode", "FAILFAST").csv(source_path)
raw.createOrReplaceTempView("raw_who")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Transform

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Write the Delta table

# COMMAND ----------

print(f"Writing {target_table} to {target_path}")
(df.write.format("delta").mode("overwrite").option("path", target_path).saveAsTable(target_table))
print(f"Written: {target_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Optimize the Delta files

# COMMAND ----------

spark.sql(f"OPTIMIZE {target_table}")
print(f"Optimized: {target_table} at {target_path}")
