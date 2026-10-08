"""Instructor setup commands; students execute notebooks in Databricks and author ADF in Studio."""

import argparse
import json
import sys
from pathlib import Path

from provisioner.config import load_settings


def _deploy(settings, resources):
    from provisioner.databricks import configure_storage, deploy_notebooks
    from provisioner.storage import upload_fixture

    settings.validate_databricks()
    print("Configuring Unity Catalog access to Azure Storage…", flush=True)
    configure_storage(settings, resources)
    print("Uploading the sales CSV…", flush=True)
    upload_fixture(
        settings,
        settings.root / "databricks-etl-pipeline/data/sales.csv",
        resources["storage_account_key"],
    )
    print("Uploading all notebooks and utilities…", flush=True)
    deploy_notebooks(settings)
    return {
        "databricks_host": settings.databricks_host,
        "notebook_path": settings.notebook_path,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up the online Databricks course example")
    parser.add_argument("--env", type=Path, help="Optional .env path (default: repository root)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("setup", "Provision Azure resources, configure storage access and upload notebooks"),
        ("provision", "Provision Azure resources automatically through Terraform"),
        ("deploy", "Configure Databricks storage access and upload notebooks"),
    ]:
        commands.add_parser(name, help=help_text)
    cleanup = commands.add_parser("cleanup", help="Destroy the Azure resources managed by this repository")
    cleanup.add_argument("--confirm-resource-group", required=True)
    args = parser.parse_args(argv)
    settings = None
    try:
        settings = load_settings(args.env)
        settings.validate_cloud()
        from provisioner.terraform import cleanup_resources, provision_resources, public_resources, resources

        if args.command == "cleanup":
            cleanup_resources(settings, args.confirm_resource_group)
            result = {"destroyed_resource_group": settings.resource_group}
        elif args.command in ("setup", "provision"):
            if args.command == "setup":
                settings.validate_databricks()
            provisioned = provision_resources(settings)
            result = provisioned if args.command == "setup" else public_resources(provisioned)
            if args.command == "setup":
                result = _deploy(settings, result)
        else:
            result = _deploy(settings, resources(settings))
        print(json.dumps(result, indent=2, default=str))
    except Exception as error:
        message = str(error)
        if settings:
            for secret in (settings.client_secret, settings.databricks_token):
                if secret:
                    message = message.replace(secret, "[REDACTED]")
        print(f"Error: {message}", file=sys.stderr)
        raise SystemExit(1) from None
