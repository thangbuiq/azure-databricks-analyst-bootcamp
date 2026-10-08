"""Instructor setup commands; students execute the notebook in Databricks."""

import argparse
import json
import sys
from pathlib import Path

from adf.deploy import pipeline_names
from provisioner.config import load_settings


def _deploy(settings, resources, with_pipelines=False):
    from adf.defs import discover_pipelines
    from adf.deploy import build_pipelines, deploy_pipelines
    from provisioner.databricks import configure_storage, deploy_notebooks
    from provisioner.storage import upload_fixture

    settings.validate_databricks()
    pipelines = discover_pipelines() if with_pipelines else ()
    built = build_pipelines(settings, pipelines)
    print("Configuring Unity Catalog access to Azure Storage…", flush=True)
    configure_storage(settings, resources)
    print("Uploading the 10-row CSV…", flush=True)
    upload_fixture(
        settings,
        settings.root / "databricks-etl-pipeline/data/sales.csv",
        resources["storage_account_key"],
    )
    print("Uploading all notebooks and utilities…", flush=True)
    deploy_notebooks(settings, resources)
    print("Creating the ADF linked services and discovered pipelines…", flush=True)
    deploy_pipelines(settings, resources, built)
    return {
        "databricks_host": settings.databricks_host,
        "notebook_path": settings.notebook_path,
        "pipelines": list(pipeline_names(pipelines)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up the online Databricks course example")
    parser.add_argument("--env", type=Path, help="Optional .env path (default: repository root)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("setup", "Provision Azure, storage access, linked services and notebooks"),
        ("provision", "Provision Azure automatically through Terraform"),
        ("deploy", "Configure storage access, linked services and upload notebooks"),
    ]:
        command = commands.add_parser(name, help=help_text)
        if name != "provision":
            command.add_argument("--with-pipelines", action="store_true", help="Deploy optional pl_*.py definitions")
    run = commands.add_parser("run-adf", help="Run an ADF pipeline and wait for its result")
    run.add_argument(
        "pipeline",
        nargs="?",
        default="pl_master_etl",
        help="ADF pipeline name, including pipelines made in Studio (default: pl_master_etl)",
    )
    run.add_argument("--parameters", type=json.loads, default={}, help="Pipeline parameters as a JSON object")
    status = commands.add_parser("status", help="Inspect an ADF run")
    status.add_argument("run_id")
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
                from adf.defs import discover_pipelines

                settings.validate_databricks()
                if args.with_pipelines:
                    from adf.deploy import build_pipelines

                    build_pipelines(settings, discover_pipelines())
            provisioned = provision_resources(settings)
            result = provisioned if args.command == "setup" else public_resources(provisioned)
            if args.command == "setup":
                result = _deploy(settings, result, args.with_pipelines)
        elif args.command == "deploy":
            result = _deploy(settings, resources(settings), args.with_pipelines)
        elif args.command == "run-adf":
            from adf.runs import run_pipeline, wait_for_pipeline

            if not isinstance(args.parameters, dict):
                raise ValueError("--parameters must be a JSON object")
            run_id = run_pipeline(settings, args.pipeline, args.parameters)
            print(f"ADF run ID: {run_id}", flush=True)
            run = wait_for_pipeline(settings, run_id)
            result = {"run_id": run_id, "status": run.status}
        else:
            from adf.deploy import factory_client

            run = factory_client(settings).pipeline_runs.get(
                settings.resource_group, settings.factory_name, args.run_id
            )
            result = {"run_id": args.run_id, "status": run.status, "message": run.message}
        print(json.dumps(result, indent=2, default=str))
    except Exception as error:
        message = str(error)
        if settings:
            for secret in (settings.client_secret, settings.databricks_token):
                if secret:
                    message = message.replace(secret, "[REDACTED]")
        print(f"Error: {message}", file=sys.stderr)
        raise SystemExit(1) from None
