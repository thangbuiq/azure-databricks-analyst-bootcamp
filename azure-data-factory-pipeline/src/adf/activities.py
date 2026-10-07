"""Reusable steps for Python-defined ADF pipelines."""

from hashlib import sha256

from azure.mgmt.datafactory import models as m


def _depends_on(after):
    return [m.ActivityDependency(activity=after, dependency_conditions=["Succeeded"])] if after else []


def run_databricks_job(settings, *, name, job_id, after=None):
    """Return start/wait/check activities; the next step depends on name + '_check'."""
    start = f"{name}_start"
    wait = f"{name}_wait"
    status = f"{name}_status"
    interval = f"{name}_poll_interval"
    # Separate jobs in one pipeline run, with stable retry tokens below 64 characters.
    token_suffix = sha256(name.encode()).hexdigest()[:16]
    return [
        m.WebActivity(
            name=start,
            depends_on=_depends_on(after),
            method="POST",
            url=settings.databricks_host + "/api/2.2/jobs/run-now",
            headers={
                "Authorization": "Bearer " + settings.databricks_token,
                "Content-Type": "application/json",
            },
            body={"job_id": int(job_id), "idempotency_token": "@{pipeline().RunId}-" + token_suffix},
            policy=m.ActivityPolicy(
                secure_input=True,
                retry=settings.adf_api_retries,
                retry_interval_in_seconds=settings.adf_api_retry_interval_seconds,
            ),
        ),
        m.UntilActivity(
            name=wait,
            depends_on=_depends_on(start),
            timeout="01:00:00",
            expression=m.Expression(
                type="Expression",
                value="@contains(createArray('TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'), "
                f"activity('{status}').output.state.life_cycle_state)",
            ),
            activities=[
                m.WaitActivity(name=interval, wait_time_in_seconds=30),
                m.WebActivity(
                    name=status,
                    method="GET",
                    depends_on=_depends_on(interval),
                    url=m.Expression(
                        type="Expression",
                        value=f"@concat('{settings.databricks_host}/api/2.2/jobs/runs/get?run_id=', "
                        f"string(activity('{start}').output.run_id))",
                    ),
                    headers={"Authorization": "Bearer " + settings.databricks_token},
                    policy=m.ActivityPolicy(
                        secure_input=True,
                        retry=settings.adf_api_retries,
                        retry_interval_in_seconds=settings.adf_api_retry_interval_seconds,
                    ),
                ),
            ],
        ),
        m.IfConditionActivity(
            name=f"{name}_check",
            depends_on=_depends_on(wait),
            expression=m.Expression(
                type="Expression",
                value=f"@equals(activity('{status}').output.state.result_state, 'SUCCESS')",
            ),
            if_false_activities=[
                m.FailActivity(
                    name=f"{name}_failed",
                    message="Databricks job did not succeed. Inspect its run in the workspace.",
                    error_code="DatabricksJobFailed",
                )
            ],
        ),
    ]


def copy_file(*, name, source, destination, after=None):
    """Copy bytes from an HTTP BinaryDataset to an Azure Blob BinaryDataset by dataset name."""
    return m.CopyActivity(
        name=name,
        depends_on=_depends_on(after),
        source=m.BinarySource(store_settings=m.HttpReadSettings(request_method="GET")),
        sink=m.BinarySink(store_settings=m.AzureBlobStorageWriteSettings()),
        inputs=[m.DatasetReference(type="DatasetReference", reference_name=source)],
        outputs=[m.DatasetReference(type="DatasetReference", reference_name=destination)],
    )


def execute_pipeline(*, name, pipeline, after=None):
    """Run a registered child pipeline and wait for it to finish."""
    return m.ExecutePipelineActivity(
        name=name,
        depends_on=_depends_on(after),
        pipeline=m.PipelineReference(type="PipelineReference", reference_name=pipeline),
        wait_on_completion=True,
    )
