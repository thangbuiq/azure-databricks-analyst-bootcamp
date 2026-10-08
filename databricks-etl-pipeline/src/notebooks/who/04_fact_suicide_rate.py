# Databricks notebook source
# ruff: noqa: F821
# MAGIC %md
# MAGIC # WHO — fact_suicide_rate
# MAGIC Read Azure data and write one Delta table.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Locations
# MAGIC Edit these values directly if your account or table changes.

# COMMAND ----------

target_table = "workspace.dm_who.fact_suicide_rate"
target_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_who/fact_suicide_rate"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Transform

# COMMAND ----------

df = spark.sql("""
    SELECT c.country_year_key, d.demographic_key, s.suicide_rate_per_100k
    FROM workspace.dm_who.stg_suicide s
    JOIN workspace.dm_who.dim_country_year c
      ON s.country_code = c.country_code AND s.year = c.year
    JOIN workspace.dm_who.dim_demographic d
      ON s.sex = d.sex AND s.age_bracket = d.age_bracket AND s.generation = d.generation
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
