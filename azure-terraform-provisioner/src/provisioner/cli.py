"""Instructor setup commands; students execute the notebook in Databricks."""

import argparse
import json
import sys
from pathlib import Path

from adf.deploy import pipeline_names
from provisioner.config import load_settings


def _deploy(settings, resources):
    from adf.defs import discover_jobs, discover_pipelines
    from adf.deploy import deploy_pipelines
    from provisioner.databricks import deploy_notebooks
    from provisioner.storage import upload_fixture

    settings.validate_databricks()
    pipelines = discover_pipelines()
    discover_jobs(pipelines, settings.notebook_source_dir)
    print("Uploading the 10-row CSV…", flush=True)
    upload_fixture(
        settings,
        settings.root / "databricks-etl-pipeline/data/sales.csv",
        resources["storage_account_key"],
    )
    print("Uploading all notebooks and utilities…", flush=True)
    job_ids = deploy_notebooks(settings, resources, pipelines)
    print("Creating the ADF linked services and discovered pipelines…", flush=True)
    deploy_pipelines(settings, resources, job_ids, pipelines)
    return {
        "databricks_host": settings.databricks_host,
        "databricks_jobs": job_ids,
        "notebook_path": settings.notebook_path,
        "pipelines": list(pipeline_names(pipelines)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up the online Databricks course example")
    parser.add_argument("--env", type=Path, help="Optional .env path (default: repository root)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("setup", "Provision Azure, then deploy all declared jobs and pipelines"),
        ("provision", "Provision Azure automatically through Terraform"),
        ("deploy", "Upload the notebook/data and update ADF pipelines"),
    ]:
        commands.add_parser(name, help=help_text)
    run = commands.add_parser("run-adf", help="Run an ADF pipeline and wait for its result")
    run.add_argument(
        "pipeline",
        nargs="?",
        default="pl_master_etl",
        help="Discovered pipeline name (default: pl_master_etl)",
    )
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
                from adf.defs import discover_jobs, discover_pipelines

                settings.validate_databricks()
                discover_jobs(discover_pipelines(), settings.notebook_source_dir)
            provisioned = provision_resources(settings)
            result = provisioned if args.command == "setup" else public_resources(provisioned)
            if args.command == "setup":
                result = _deploy(settings, result)
        elif args.command == "deploy":
            result = _deploy(settings, resources(settings))
        elif args.command == "run-adf":
            from adf.runs import run_pipeline, wait_for_pipeline

            run_id = run_pipeline(settings, args.pipeline)
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
