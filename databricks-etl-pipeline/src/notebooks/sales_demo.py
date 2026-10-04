# Databricks notebook source
# MAGIC %md
# MAGIC # Ten-row sales: Bronze → Silver → Gold → Parquet
# MAGIC All Spark logic is here. ADF executes this notebook by its workspace path.

# COMMAND ----------
"""PySpark transformations: run this notebook in the Databricks workspace."""

from functools import reduce
from urllib.parse import urlparse

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# Deployment fills these non-secret widget defaults from the root .env.
DEFAULT_PARAMETERS = {}
COLUMNS = ["sale_id", "sale_date", "product", "category", "quantity", "unit_price"]


def clean_sales(raw: DataFrame) -> DataFrame:
    missing = set(COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError("Invalid input: missing columns " + ", ".join(sorted(missing)))
    # try_cast avoids session-dependent ANSI exceptions; validation remains explicit.
    data = raw.select(*[F.trim(F.col(c)).alias(c) for c in COLUMNS])
    syntax = (
        F.col("sale_id").rlike(r"^[0-9]+$")
        & F.col("quantity").rlike(r"^[0-9]+$")
        & F.col("unit_price").rlike(r"^[0-9]+(\.[0-9]{1,2})?$")
        & F.col("sale_date").rlike(r"^\d{4}-\d{2}-\d{2}$")
    )
    if data.filter(~F.coalesce(syntax, F.lit(False))).limit(1).count():
        raise ValueError("Invalid sales row: malformed ID, quantity, date or price")
    # selectExpr only performs safe type conversion; all transformations are PySpark.
    typed = data.select(
        F.expr("try_cast(sale_id as bigint)").alias("sale_id"),
        F.expr("try_cast(sale_date as date)").alias("sale_date"),
        F.col("product"),
        F.lower("category").alias("category"),
        F.expr("try_cast(quantity as int)").alias("quantity"),
        F.expr("try_cast(unit_price as decimal(12,2))").alias("unit_price"),
    )
    invalid = reduce(lambda a, b: a | b, [F.col(c).isNull() for c in COLUMNS])
    invalid = invalid | (F.col("sale_id") <= 0) | (F.col("quantity") <= 0) | (F.col("unit_price") < 0)
    invalid = invalid | (F.length("product") == 0) | (F.length("category") == 0)
    if typed.filter(invalid).limit(1).count():
        raise ValueError("Invalid sales row: required field or numeric/date range")
    if typed.groupBy("sale_id").count().filter(F.col("count") > 1).limit(1).count():
        raise ValueError("Duplicate sale IDs")
    return typed.withColumn("revenue", (F.col("quantity") * F.col("unit_price")).cast("decimal(24,2)"))


def aggregate_sales(silver: DataFrame) -> DataFrame:
    return silver.groupBy("sale_date", "category").agg(
        F.sum("quantity").alias("units"),
        F.sum("revenue").alias("revenue"),
        F.count("*").alias("sale_count"),
    )


# COMMAND ----------
"""Four idempotent stages. Output paths are dedicated demo datasets."""

STAGES = ("bronze", "silver", "gold", "export")


def _validate_paths(lakehouse_path: str, report_path: str):
    for path in (lakehouse_path, report_path):
        parsed = urlparse(path)
        if parsed.path.rstrip("/") in ("", ".", "..") or ".." in parsed.path.split("/"):
            raise ValueError("Use a dedicated dataset path; never a filesystem/container root")
    if lakehouse_path.rstrip("/") == report_path.rstrip("/"):
        raise ValueError("Use separate dedicated lakehouse and reporting paths")


def run_stage(spark, stage: str, raw_path: str, lakehouse_path: str, report_path: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    _validate_paths(lakehouse_path, report_path)
    paths = {name: f"{lakehouse_path.rstrip('/')}/{name}" for name in STAGES[:3]}
    if stage == "bronze":
        frame = (
            spark.read.option("header", True)
            .option("mode", "FAILFAST")
            .schema(",".join(f"{c} string" for c in COLUMNS))
            .csv(raw_path)
        )
        if frame.count() != 10:
            raise ValueError("The demo expects exactly 10 source rows")
    elif stage == "silver":
        frame = clean_sales(spark.read.format("delta").load(paths["bronze"]))
    elif stage == "gold":
        frame = aggregate_sales(spark.read.format("delta").load(paths["silver"]))
    else:
        frame = spark.read.format("delta").load(paths["gold"])
        frame.coalesce(1).write.mode("overwrite").parquet(report_path)
        return
    frame.write.format("delta").mode("overwrite").option("overwriteSchema", True).save(paths[stage])


def check_outputs(spark, lakehouse_path: str, report_path: str) -> dict:
    tables = {n: spark.read.format("delta").load(f"{lakehouse_path}/{n}") for n in STAGES[:3]}
    report = spark.read.parquet(report_path)
    if tables["gold"].exceptAll(report).count() or report.exceptAll(tables["gold"]).count():
        raise ValueError("Report differs from Gold")
    totals = report.agg(F.sum("units").alias("units"), F.sum("revenue").alias("revenue")).first()
    actual = {
        **{f"{n}_rows": t.count() for n, t in tables.items()},
        "units": totals.units,
        "revenue": str(totals.revenue),
    }
    expected = {
        "bronze_rows": 10,
        "silver_rows": 10,
        "gold_rows": 2,
        "units": 55,
        "revenue": "550.00",
    }
    if actual != expected:
        raise ValueError(f"Demo output mismatch: {actual}")
    return actual


# COMMAND ----------
def run_notebook(spark, dbutils):
    """ADF supplies parameters; interactive runs use the deployed widget defaults."""
    names = (
        "raw_path",
        "lakehouse_path",
        "report_path",
        "storage_account",
        "tenant_id",
        "client_id",
        "secret_scope",
    )
    for name in names:
        dbutils.widgets.text(name, DEFAULT_PARAMETERS.get(name, ""))
    params = {name: dbutils.widgets.get(name) for name in names}
    missing = [name for name, value in params.items() if not value]
    if missing:
        raise ValueError("Missing notebook parameters: " + ", ".join(missing))
    account = params["storage_account"] + ".dfs.core.windows.net"
    config = {
        f"fs.azure.account.auth.type.{account}": "OAuth",
        f"fs.azure.account.oauth.provider.type.{account}": "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",
        f"fs.azure.account.oauth2.client.id.{account}": params["client_id"],
        f"fs.azure.account.oauth2.client.secret.{account}": dbutils.secrets.get(
            scope=params["secret_scope"], key="storage-client-secret"
        ),
        f"fs.azure.account.oauth2.client.endpoint.{account}": f"https://login.microsoftonline.com/{params['tenant_id']}/oauth2/token",
    }
    for key, value in config.items():
        spark.conf.set(key, value)
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    for stage in STAGES:
        print(f"Running {stage}")
        run_stage(
            spark,
            stage,
            params["raw_path"],
            params["lakehouse_path"],
            params["report_path"],
        )
    result = check_outputs(spark, params["lakehouse_path"], params["report_path"])
    import json

    dbutils.notebook.exit(json.dumps(result))


# COMMAND ----------
# Run All in Databricks executes the full example and its output checks.
if "dbutils" in globals() and "spark" in globals():
    run_notebook(globals()["spark"], globals()["dbutils"])
