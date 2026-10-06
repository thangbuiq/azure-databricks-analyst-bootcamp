"""Run the deployed Databricks serverless job."""

from azure.mgmt.datafactory import models as m

from adf.connections import AZURE_REPORT, VOLUME_REPORT

NAME = "pl_sales_pipeline"


def build_pipeline(settings) -> m.PipelineResource:
    return m.PipelineResource(
        description="Run the serverless notebook, then copy its Parquet report from the volume to Azure.",
        concurrency=1,
        activities=[
            m.WebActivity(
                name="run_sales_serverless_job",
                method="POST",
                url=settings.databricks_host + "/api/2.2/jobs/run-now",
                headers={
                    "Authorization": "Bearer " + settings.databricks_token,
                    "Content-Type": "application/json",
                },
                body={
                    "job_id": int(settings.databricks_job_id),
                    "idempotency_token": "@{pipeline().RunId}",
                },
                policy=m.ActivityPolicy(secure_input=True, retry=1),
            ),
            m.UntilActivity(
                name="wait_for_job",
                depends_on=[
                    m.ActivityDependency(
                        activity="run_sales_serverless_job",
                        dependency_conditions=["Succeeded"],
                    )
                ],
                timeout="01:00:00",
                expression=m.Expression(
                    type="Expression",
                    value="@contains(createArray('TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'), activity('get_job_status').output.state.life_cycle_state)",
                ),
                activities=[
                    m.WaitActivity(name="poll_interval", wait_time_in_seconds=30),
                    m.WebActivity(
                        name="get_job_status",
                        method="GET",
                        depends_on=[
                            m.ActivityDependency(
                                activity="poll_interval",
                                dependency_conditions=["Succeeded"],
                            )
                        ],
                        url=m.Expression(
                            type="Expression",
                            value="@concat('"
                            + settings.databricks_host
                            + "/api/2.2/jobs/runs/get?run_id=', string(activity('run_sales_serverless_job').output.run_id))",
                        ),
                        headers={"Authorization": "Bearer " + settings.databricks_token},
                        policy=m.ActivityPolicy(secure_input=True, retry=1),
                    ),
                ],
            ),
            m.IfConditionActivity(
                name="check_job_result",
                depends_on=[m.ActivityDependency(activity="wait_for_job", dependency_conditions=["Succeeded"])],
                expression=m.Expression(
                    type="Expression",
                    value="@equals(activity('get_job_status').output.state.result_state, 'SUCCESS')",
                ),
                if_false_activities=[
                    m.FailActivity(
                        name="job_failed",
                        message="Databricks job did not succeed. Inspect its run in the workspace.",
                        error_code="DatabricksJobFailed",
                    )
                ],
            ),
            m.CopyActivity(
                name="copy_report_to_azure",
                depends_on=[m.ActivityDependency(activity="check_job_result", dependency_conditions=["Succeeded"])],
                source=m.BinarySource(store_settings=m.HttpReadSettings(request_method="GET")),
                sink=m.BinarySink(store_settings=m.AzureBlobStorageWriteSettings()),
                inputs=[m.DatasetReference(type="DatasetReference", reference_name=VOLUME_REPORT)],
                outputs=[m.DatasetReference(type="DatasetReference", reference_name=AZURE_REPORT)],
            ),
        ],
    )
