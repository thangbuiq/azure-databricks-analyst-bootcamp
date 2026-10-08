# Databricks notebook source
# ruff: noqa: F821
DEFAULT_PARAMETERS = {}
dbutils.widgets.text("catalog", DEFAULT_PARAMETERS.get("catalog", "workspace"))
dbutils.widgets.text("who_lakehouse_path", DEFAULT_PARAMETERS.get("who_lakehouse_path", ""))
catalog = dbutils.widgets.get("catalog")
lakehouse_path = dbutils.widgets.get("who_lakehouse_path")
assert lakehouse_path.startswith("abfss://"), "Set who_lakehouse_path to the Azure lakehouse/dm_who path"

# COMMAND ----------
df = spark.sql(f"""
    SELECT c.country_year_key, d.demographic_key, s.suicide_rate_per_100k
    FROM {catalog}.dm_who.stg_suicide s
    JOIN {catalog}.dm_who.dim_country_year c
      ON s.country_code = c.country_code AND s.year = c.year
    JOIN {catalog}.dm_who.dim_demographic d
      ON s.sex = d.sex AND s.age_bracket = d.age_bracket AND s.generation = d.generation
""")

assert df.count() == 18315
assert df.select("country_year_key", "demographic_key").distinct().count() == 18315

(
    df.write.format("delta")
    .mode("overwrite")
    .option("path", lakehouse_path + "/fact_suicide_rate")
    .saveAsTable(f"{catalog}.dm_who.fact_suicide_rate")
)
display(df.limit(10))
