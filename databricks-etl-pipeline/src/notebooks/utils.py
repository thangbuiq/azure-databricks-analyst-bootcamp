"""Shared notebook helpers; uploaded as a regular Python workspace file."""

from urllib.parse import urlparse


def setup_storage(spark, dbutils, defaults):
    """Read notebook widgets and configure Azure storage using a secret scope."""
    names = ("raw_path", "lakehouse_path", "report_path", "storage_account", "secret_scope")
    for name in names:
        dbutils.widgets.text(name, defaults.get(name, ""))
    params = {name: dbutils.widgets.get(name) for name in names}
    missing = [name for name, value in params.items() if not value]
    if missing:
        raise ValueError("Missing notebook parameters: " + ", ".join(missing))
    if params["lakehouse_path"].rstrip("/") == params["report_path"].rstrip("/"):
        raise ValueError("Use separate lakehouse and reporting paths")
    account = params["storage_account"] + ".dfs.core.windows.net"
    storage_key = dbutils.secrets.get(scope=params["secret_scope"], key="storage-account-key")
    spark.conf.set(f"fs.azure.account.key.{account}", storage_key)
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    return params


def write_data(frame, path, format="delta"):
    """Replace a dedicated dataset with Delta or Parquet output."""
    parsed = urlparse(path)
    if parsed.path.rstrip("/") in ("", ".", "..") or ".." in parsed.path.split("/"):
        raise ValueError("Use a dedicated dataset path, never a filesystem/container root")
    if format not in ("delta", "parquet"):
        raise ValueError("Use delta or parquet")
    writer = frame.write.format(format).mode("overwrite")
    if format == "delta":
        writer = writer.option("overwriteSchema", True)
    writer.save(path)
