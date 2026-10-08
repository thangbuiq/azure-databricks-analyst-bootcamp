"""Configuration defaults live here; .env contains credentials and deployment inputs."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

TERRAFORM_VERSION = "1.11.4"


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "azure-terraform-provisioner").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise ValueError("Run commands from an editable repository install (uv sync).")


@dataclass(frozen=True)
class Settings:
    root: Path
    subscription_id: str = ""
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    location: str = "japaneast"
    resource_group: str = "rg-analytics-demo"
    storage_account: str = ""
    factory_name: str = "adf-analytics-demo"
    databricks_host: str = ""
    databricks_token: str = field(default="", repr=False)
    notebook_path: str = "/Shared/analytics-demo"
    databricks_catalog: str = "workspace"
    databricks_schema: str = "dm_sales"

    @property
    def storage_credential_name(self):
        return f"course_{self.storage_account}"

    def storage_url(self, container):
        return f"abfss://{container}@{self.storage_account}.dfs.core.windows.net"

    @property
    def notebook_source_dir(self):
        return self.root / "databricks-etl-pipeline/src/notebooks"

    def validate_databricks(self):
        if not self.databricks_host or not self.databricks_token:
            raise ValueError("Set DATABRICKS_HOST and DATABRICKS_TOKEN in .env before deploying")
        parsed = urlparse(self.databricks_host)
        if (
            parsed.scheme != "https"
            or not (parsed.hostname or "").endswith(".azuredatabricks.net")
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.port
        ):
            raise ValueError("DATABRICKS_HOST must be an https Azure Databricks workspace URL")

    @property
    def runtime_dir(self):
        return self.root / ".runtime"

    def validate_cloud(self):
        fields = {
            "AZURE_SUBSCRIPTION_ID": self.subscription_id,
            "AZURE_TENANT_ID": self.tenant_id,
            "AZURE_CLIENT_ID": self.client_id,
            "AZURE_CLIENT_SECRET": self.client_secret,
            "STORAGE_ACCOUNT": self.storage_account,
        }
        missing = [name for name, value in fields.items() if not value]
        if missing:
            raise ValueError("Set these values in .env: " + ", ".join(missing))
        for name, value in fields.items():
            if name not in {"AZURE_CLIENT_SECRET", "STORAGE_ACCOUNT"}:
                from uuid import UUID

                try:
                    UUID(value)
                except ValueError:
                    raise ValueError(f"{name} must be a UUID") from None


def load_settings(env_file: Path | None = None) -> Settings:
    env_file = Path(env_file).resolve() if env_file else repository_root() / ".env"
    values = dotenv_values(env_file, interpolate=False) if env_file.exists() else {}

    def get(key, default=""):
        return values.get(key) or default

    defaults = Settings(root=repository_root())
    s = Settings(
        root=defaults.root,
        subscription_id=get("AZURE_SUBSCRIPTION_ID"),
        tenant_id=get("AZURE_TENANT_ID"),
        client_id=get("AZURE_CLIENT_ID"),
        client_secret=get("AZURE_CLIENT_SECRET"),
        storage_account=get("STORAGE_ACCOUNT"),
        factory_name=get("DATA_FACTORY", defaults.factory_name),
        resource_group=get("RESOURCE_GROUP", defaults.resource_group),
        location=get("AZURE_LOCATION", defaults.location),
        databricks_host=get("DATABRICKS_HOST").rstrip("/"),
        databricks_token=get("DATABRICKS_TOKEN"),
        notebook_path=get("DATABRICKS_NOTEBOOK_PATH", defaults.notebook_path).rstrip("/"),
        databricks_catalog=get("DATABRICKS_CATALOG", defaults.databricks_catalog),
    )
    if s.storage_account and not re.fullmatch(r"[a-z0-9]{3,24}", s.storage_account):
        raise ValueError("STORAGE_ACCOUNT must be 3-24 lowercase letters/numbers")
    if not s.notebook_path.startswith("/Shared/") or ".." in s.notebook_path.split("/"):
        raise ValueError("DATABRICKS_NOTEBOOK_PATH must be a folder below /Shared/")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s.databricks_catalog):
        raise ValueError("DATABRICKS_CATALOG must contain only letters, digits and underscores")
    return s
