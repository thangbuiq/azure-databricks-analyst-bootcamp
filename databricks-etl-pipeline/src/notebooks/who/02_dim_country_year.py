# Databricks notebook source
# ruff: noqa: F821
# MAGIC %md
# MAGIC # WHO — dim_country_year
# MAGIC Read Azure data and write one Delta table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Locations
# MAGIC Edit these values directly if your account or table changes.

# COMMAND ----------

target_table = "workspace.dm_who.dim_country_year"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/dim_country_year"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Transform

# COMMAND ----------

df = spark.sql("""
    SELECT DISTINCT
        CONCAT(country_code, '_', CAST(year AS STRING)) AS country_year_key,
        country_code, country_name, year,
        gdp_usd, gdp_per_capita_usd, total_country_population
    FROM workspace.dm_who.stg_suicide
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Write the Delta table

# COMMAND ----------

print(f"Writing {target_table} to {target_path}")
(df.write.format("delta").mode("overwrite").option("path", target_path).saveAsTable(target_table))
print(f"Written: {target_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Optimize the Delta files

# COMMAND ----------

spark.sql(f"OPTIMIZE {target_table}")
print(f"Optimized: {target_table} at {target_path}")
