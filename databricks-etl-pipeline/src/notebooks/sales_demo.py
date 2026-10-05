# Databricks notebook source
# MAGIC %md
# MAGIC # Sales: Bronze → Silver → Gold → Parquet
# MAGIC Run each cell online on Serverless. Delta tables and files use Unity Catalog.
# MAGIC Deployment stages the Azure source in a volume; ADF copies the finished report back to Azure.

# COMMAND ----------
# ruff: noqa: F821
import json

from utils import setup_parameters, write_data

# Deployment fills these non-secret widget defaults from the root .env.
DEFAULT_PARAMETERS = {}
params = setup_parameters(spark, dbutils, DEFAULT_PARAMETERS)
tables = params["table_prefix"]

# COMMAND ----------
# MAGIC %md
# MAGIC ## Bronze: load the ten source rows unchanged

# COMMAND ----------
bronze = (
    spark.read.option("header", True)
    .option("mode", "FAILFAST")
    .schema("sale_id STRING, sale_date STRING, product STRING, category STRING, quantity STRING, unit_price STRING")
    .csv(params["raw_path"])
)
assert bronze.count() == 10, "Expected 10 source rows"
write_data(bronze, f"{tables}_bronze")
spark.table(f"{tables}_bronze").createOrReplaceTempView("bronze_sales")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver: clean text, convert types and calculate revenue

# COMMAND ----------
silver = spark.sql("""
    SELECT
        CAST(TRIM(sale_id) AS BIGINT) AS sale_id,
        CAST(TRIM(sale_date) AS DATE) AS sale_date,
        TRIM(product) AS product,
        LOWER(TRIM(category)) AS category,
        CAST(TRIM(quantity) AS INT) AS quantity,
        CAST(TRIM(unit_price) AS DECIMAL(12, 2)) AS unit_price,
        CAST(CAST(TRIM(quantity) AS INT) * CAST(TRIM(unit_price) AS DECIMAL(12, 2))
             AS DECIMAL(24, 2)) AS revenue
    FROM bronze_sales
""")
write_data(silver, f"{tables}_silver")
spark.table(f"{tables}_silver").createOrReplaceTempView("silver_sales")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold: summarize sales by date and category

# COMMAND ----------
gold = spark.sql("""
    SELECT sale_date, category,
           SUM(quantity) AS units,
           SUM(revenue) AS revenue,
           COUNT(*) AS sale_count
    FROM silver_sales
    GROUP BY sale_date, category
""")
write_data(gold, f"{tables}_gold")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Export and check
# MAGIC Expect 10 sales, 55 units and 550.00 revenue across two categories.

# COMMAND ----------
gold = spark.table(f"{tables}_gold")
write_data(gold, params["report_path"], format="parquet")
report = spark.read.parquet(params["report_path"])
report.createOrReplaceTempView("sales_report")
totals = spark.sql("SELECT SUM(units) AS units, SUM(revenue) AS revenue FROM sales_report").first()
assert silver.count() == 10 and report.count() == 2, "Unexpected row counts"
assert totals.units == 55 and str(totals.revenue) == "550.00", "Unexpected totals"
assert gold.exceptAll(report).count() == 0 and report.exceptAll(gold).count() == 0, "Export differs from Gold"
display(report)
dbutils.notebook.exit(
    json.dumps({"sales_rows": 10, "report_rows": 2, "units": totals.units, "revenue": str(totals.revenue)})
)
