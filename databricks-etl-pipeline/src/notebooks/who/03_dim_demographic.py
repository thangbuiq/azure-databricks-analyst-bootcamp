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
        SHA2(TO_JSON(NAMED_STRUCT(
            'sex', sex, 'age_bracket', age_bracket, 'generation', generation
        )), 256) AS demographic_key,
        sex, age_bracket, generation
    FROM {catalog}.dm_who.stg_suicide
""")

assert df.count() == 36
assert df.select("demographic_key").distinct().count() == 36

(
    df.write.format("delta")
    .mode("overwrite")
    .option("path", lakehouse_path + "/dim_demographic")
    .saveAsTable(f"{catalog}.dm_who.dim_demographic")
)
display(df)
