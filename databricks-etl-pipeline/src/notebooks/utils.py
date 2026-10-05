"""Shared serverless helpers for managed Delta tables and volume files."""

import shutil
from pathlib import Path


def setup_parameters(spark, dbutils, defaults):
    """Read the non-secret locations supplied by deployment or notebook widgets."""
    names = ("raw_path", "table_prefix", "report_path")
    for name in names:
        dbutils.widgets.text(name, defaults.get(name, ""))
    params = {name: dbutils.widgets.get(name) for name in names}
    missing = [name for name, value in params.items() if not value]
    if missing:
        raise ValueError("Missing notebook parameters: " + ", ".join(missing))
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    return params


def write_data(frame, target, format="delta"):
    """Overwrite a managed Delta table or one small Parquet file in a volume."""
    if format == "delta":
        frame.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable(target)
    elif format == "parquet":
        path = Path(target)
        if not target.startswith("/Volumes/") or ".." in path.parts or path.suffix != ".parquet":
            raise ValueError("Parquet output must be a .parquet file inside a managed volume")
        # One file keeps the ten-row course example easy to copy from ADF to Azure.
        parts = Path(target + ".parts")
        frame.coalesce(1).write.mode("overwrite").parquet(str(parts))
        files = list(parts.glob("part-*.parquet"))
        if len(files) != 1:
            raise ValueError("Expected one Parquet part for the small course dataset")
        shutil.copyfile(files[0], path)
    else:
        raise ValueError("Use delta or parquet")
