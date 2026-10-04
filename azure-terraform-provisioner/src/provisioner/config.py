"""One root .env; relative paths are anchored to its directory."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "azure-terraform-provisioner").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise ValueError("Run commands from an editable repository install (uv sync).")


@dataclass(frozen=True)
class Settings:
    root: Path
    poll_seconds: int = 15
    timeout_seconds: int = 3600
    subscription_id: str = ""
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    principal_object_id: str = ""
    location: str = "southeastasia"
    resource_group: str = "rg-analytics-demo"
    storage_account: str = ""
    workspace_name: str = "dbw-analytics-demo"
    factory_name: str = "adf-analytics-demo"
    account_id: str = ""
    runtime: str = "16.4.x-scala2.12"
    node_type: str = "Standard_D4ds_v5"
    notebook_path: str = "/Shared/analytics-demo/sales_demo"
    secret_scope: str = "analytics-demo"
    policy_id: str = ""

    @property
    def runtime_dir(self):
        return self.root / ".runtime"

    def validate_cloud(self):
        fields = {
            "AZURE_SUBSCRIPTION_ID": self.subscription_id,
            "AZURE_TENANT_ID": self.tenant_id,
            "AZURE_CLIENT_ID": self.client_id,
            "AZURE_CLIENT_SECRET": self.client_secret,
            "AZURE_PRINCIPAL_OBJECT_ID": self.principal_object_id,
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

    s = Settings(
        root=repository_root(),
        poll_seconds=int(get("POLL_SECONDS", "15")),
        timeout_seconds=int(get("TIMEOUT_SECONDS", "3600")),
        subscription_id=get("AZURE_SUBSCRIPTION_ID"),
        tenant_id=get("AZURE_TENANT_ID"),
        client_id=get("AZURE_CLIENT_ID"),
        client_secret=get("AZURE_CLIENT_SECRET"),
        principal_object_id=get("AZURE_PRINCIPAL_OBJECT_ID"),
        location=get("AZURE_LOCATION", "southeastasia"),
        resource_group=get("RESOURCE_GROUP", "rg-analytics-demo"),
        storage_account=get("STORAGE_ACCOUNT"),
        workspace_name=get("DATABRICKS_WORKSPACE", "dbw-analytics-demo"),
        factory_name=get("DATA_FACTORY", "adf-analytics-demo"),
        account_id=get("DATABRICKS_ACCOUNT_ID"),
        runtime=get("DATABRICKS_RUNTIME", "16.4.x-scala2.12"),
        node_type=get("DATABRICKS_NODE_TYPE", "Standard_D4ds_v5"),
        notebook_path=get("DATABRICKS_NOTEBOOK_PATH", "/Shared/analytics-demo/sales_demo"),
        secret_scope=get("DATABRICKS_SECRET_SCOPE", "analytics-demo"),
        policy_id=get("DATABRICKS_POLICY_ID"),
    )
    if s.poll_seconds <= 0 or s.timeout_seconds <= 0:
        raise ValueError("POLL_SECONDS and TIMEOUT_SECONDS must be positive")
    if s.storage_account and not re.fullmatch(r"[a-z0-9]{3,24}", s.storage_account):
        raise ValueError("STORAGE_ACCOUNT must be 3-24 lowercase letters/numbers")
    if not s.notebook_path.startswith("/Shared/") or ".." in s.notebook_path.split("/"):
        raise ValueError("DATABRICKS_NOTEBOOK_PATH must be a notebook below /Shared/")
    return s


def notebook_parameters(settings):
    account = settings.storage_account + ".dfs.core.windows.net"
    return {
        "raw_path": f"abfss://raw@{account}/sales/sales.csv",
        "lakehouse_path": f"abfss://lakehouse@{account}/sales",
        "report_path": f"abfss://reports@{account}/sales",
        "storage_account": settings.storage_account,
        "tenant_id": settings.tenant_id,
        "client_id": settings.client_id,
        "secret_scope": settings.secret_scope,
    }
