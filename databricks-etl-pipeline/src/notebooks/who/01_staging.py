# Databricks notebook source
# ruff: noqa: F821
DEFAULT_PARAMETERS = {}
dbutils.widgets.text("catalog", DEFAULT_PARAMETERS.get("catalog", "workspace"))
dbutils.widgets.text("who_lakehouse_path", DEFAULT_PARAMETERS.get("who_lakehouse_path", ""))
catalog = dbutils.widgets.get("catalog")
lakehouse_path = dbutils.widgets.get("who_lakehouse_path")
assert lakehouse_path.startswith("abfss://"), "Set who_lakehouse_path to the Azure lakehouse/dm_who path"
dbutils.widgets.text("who_raw_path", DEFAULT_PARAMETERS.get("who_raw_path", ""))
raw_path = dbutils.widgets.get("who_raw_path")
assert raw_path.startswith("abfss://"), "Set who_raw_path to the Azure CSV path"

# COMMAND ----------
raw = spark.read.option("header", True).option("inferSchema", False).option("mode", "FAILFAST").csv(raw_path)
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

(
    df.write.format("delta")
    .mode("overwrite")
    .option("path", lakehouse_path + "/stg_suicide")
    .saveAsTable(f"{catalog}.dm_who.stg_suicide")
)
display(df.limit(10))
