# Databricks notebook source

# MAGIC %md
# MAGIC # Sales — Bronze → Silver → Gold
# MAGIC Read Azure Storage, write Delta tables, then export Gold as Parquet.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Locations
# MAGIC Edit these values directly if your account or tables change.

# COMMAND ----------

source_path = "abfss://raw@bdastorageaccountmaster.dfs.core.windows.net/sales/sales.csv"
bronze_table = "bnstprod.dm_sales.analytics_demo_sales_bronze"
silver_table = "bnstprod.dm_sales.analytics_demo_sales_silver"
gold_table = "bnstprod.dm_sales.analytics_demo_sales_gold"
bronze_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_sales/sales_bronze"
silver_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_sales/sales_silver"
gold_path = "abfss://lakehouse@bdastorageaccountmaster.dfs.core.windows.net/dm_sales/sales_gold"
report_path = "abfss://reports@bdastorageaccountmaster.dfs.core.windows.net/sales"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Read Bronze
# MAGIC Keep the source values as strings.

# COMMAND ----------

bronze = (
    spark.read.option("header", True)
    .option("mode", "FAILFAST")
    .schema("sale_id STRING, sale_date STRING, product STRING, category STRING, quantity STRING, unit_price STRING")
    .csv(source_path)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Write Bronze

# COMMAND ----------

print(f"Writing {bronze_table} to {bronze_path}")
(bronze.write.format("delta").mode("overwrite").option("path", bronze_path).saveAsTable(bronze_table))
print(f"Written: {bronze_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Optimize Bronze

# COMMAND ----------

spark.sql(f"OPTIMIZE {bronze_table}")
print(f"Optimized: {bronze_table} at {bronze_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Transform Silver

# COMMAND ----------

silver = spark.sql(f"""
    SELECT
        CAST(TRIM(sale_id) AS BIGINT) AS sale_id,
        CAST(TRIM(sale_date) AS DATE) AS sale_date,
        TRIM(product) AS product,
        LOWER(TRIM(category)) AS category,
        CAST(TRIM(quantity) AS INT) AS quantity,
        CAST(TRIM(unit_price) AS DECIMAL(12, 2)) AS unit_price,
        CAST(CAST(TRIM(quantity) AS INT) * CAST(TRIM(unit_price) AS DECIMAL(12, 2))
             AS DECIMAL(24, 2)) AS revenue
    FROM {bronze_table}
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Write Silver

# COMMAND ----------

print(f"Writing {silver_table} to {silver_path}")
(silver.write.format("delta").mode("overwrite").option("path", silver_path).saveAsTable(silver_table))
print(f"Written: {silver_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Optimize Silver

# COMMAND ----------

spark.sql(f"OPTIMIZE {silver_table}")
print(f"Optimized: {silver_table} at {silver_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Transform Gold

# COMMAND ----------

gold = spark.sql(f"""
    SELECT sale_date, category,
           SUM(quantity) AS units,
           SUM(revenue) AS revenue,
           COUNT(*) AS sale_count
    FROM {silver_table}
    GROUP BY sale_date, category
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Write Gold

# COMMAND ----------

print(f"Writing {gold_table} to {gold_path}")
(gold.write.format("delta").mode("overwrite").option("path", gold_path).saveAsTable(gold_table))
print(f"Written: {gold_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Optimize Gold

# COMMAND ----------

spark.sql(f"OPTIMIZE {gold_table}")
print(f"Optimized: {gold_table} at {gold_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Export Gold to Parquet
# MAGIC The output folder contains Spark Parquet part files for reporting.

# COMMAND ----------

print(f"Writing Parquet report to {report_path}")
spark.table(gold_table).write.mode("overwrite").parquet(report_path)
print(f"Written: {report_path}")
