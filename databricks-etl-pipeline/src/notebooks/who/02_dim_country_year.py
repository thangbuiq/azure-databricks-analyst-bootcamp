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
    SELECT DISTINCT
        CONCAT(country_code, '_', CAST(year AS STRING)) AS country_year_key,
        country_code, country_name, year,
        gdp_usd, gdp_per_capita_usd, total_country_population
    FROM {catalog}.dm_who.stg_suicide
""")

assert df.count() == 4070
assert df.select("country_year_key").distinct().count() == 4070
assert df.filter("gdp_usd IS NULL").count() == 50

(
    df.write.format("delta")
    .mode("overwrite")
    .option("path", lakehouse_path + "/dim_country_year")
    .saveAsTable(f"{catalog}.dm_who.dim_country_year")
)
display(df.limit(10))
