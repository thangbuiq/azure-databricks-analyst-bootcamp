from adf.deploy import factory_client, pipeline_names
from provisioner.polling import wait_until


def run_pipeline(settings, pipeline_name):
    names = pipeline_names()
    if pipeline_name not in names:
        raise ValueError("Choose a registered pipeline: " + ", ".join(names))
    return (
        factory_client(settings)
        .pipelines.create_run(settings.resource_group, settings.factory_name, pipeline_name)
        .run_id
    )


def wait_for_pipeline_client(client, resource_group, factory_name, run_id, timeout_seconds, poll_seconds):
    run = wait_until(
        lambda: client.pipeline_runs.get(resource_group, factory_name, run_id),
        lambda value: value.status in {"Succeeded", "Failed", "Cancelled"},
        timeout_seconds,
        poll_seconds,
    )
    if run.status != "Succeeded":
        raise RuntimeError(
            f"ADF run {run_id}: {run.status}. {run.message or 'Inspect ADF Monitor for activity errors.'}"
        )
    return run


def wait_for_pipeline(settings, run_id):
    return wait_for_pipeline_client(
        factory_client(settings),
        settings.resource_group,
        settings.factory_name,
        run_id,
        settings.timeout_seconds + 180,
        settings.poll_seconds,
    )
