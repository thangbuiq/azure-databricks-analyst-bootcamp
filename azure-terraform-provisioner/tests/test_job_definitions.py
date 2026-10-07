import importlib
import sys

import pytest


def _package(tmp_path, monkeypatch, files):
    name = "defs_" + tmp_path.name.replace("-", "_")
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text("")
    for filename, source in files.items():
        (package / filename).write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    return name


def test_discovers_pipeline_files_and_orders_children_before_parents(tmp_path, monkeypatch):
    from adf.defs import discover_pipelines

    package = _package(
        tmp_path,
        monkeypatch,
        {
            "pl_parent.py": """
NAME = "parent"
PIPELINE_DEPENDENCIES = ("child",)
def build_pipeline(settings, job_ids): pass
""",
            "pl_child.py": """
NAME = "child"
def build_pipeline(settings, job_ids): pass
""",
            "helper.py": "raise AssertionError('must not import non-pipeline modules')\n",
        },
    )

    assert [module.NAME for module in discover_pipelines(package)] == ["child", "parent"]


@pytest.mark.parametrize(
    ("files", "message"),
    [
        (
            {
                "pl_one.py": 'NAME = "same"\ndef build_pipeline(settings, job_ids): pass\n',
                "pl_two.py": 'NAME = "same"\ndef build_pipeline(settings, job_ids): pass\n',
            },
            "Duplicate ADF pipeline name: same",
        ),
        (
            {
                "pl_one.py": 'NAME = "one"\nPIPELINE_DEPENDENCIES = ("missing",)\n'
                "def build_pipeline(settings, job_ids): pass\n"
            },
            "Pipeline one depends on unknown pipeline: missing",
        ),
        (
            {
                "pl_one.py": 'NAME = "one"\nPIPELINE_DEPENDENCIES = ("two",)\n'
                "def build_pipeline(settings, job_ids): pass\n",
                "pl_two.py": 'NAME = "two"\nPIPELINE_DEPENDENCIES = ("one",)\n'
                "def build_pipeline(settings, job_ids): pass\n",
            },
            "Cyclic ADF pipeline dependencies",
        ),
        (
            {"pl_old.py": 'NAME = "old"\ndef build_pipeline(settings): pass\n'},
            "must accept settings and job_ids",
        ),
    ],
)
def test_rejects_invalid_pipeline_discovery(tmp_path, monkeypatch, files, message):
    from adf.defs import discover_pipelines

    package = _package(tmp_path, monkeypatch, files)
    with pytest.raises(ValueError, match=message):
        discover_pipelines(package)


def test_string_notebook_paths_create_sequential_tasks():
    from adf.jobs import serverless_job

    job = serverless_job(
        "course-who-etl",
        notebooks=("who/01_staging", "who/02_dim_country_year", "who/03_dim_demographic"),
    )

    assert [(task.task_key, task.notebook_path, task.after) for task in job.tasks] == [
        ("01_staging", "who/01_staging", None),
        ("02_dim_country_year", "who/02_dim_country_year", "01_staging"),
        ("03_dim_demographic", "who/03_dim_demographic", "02_dim_country_year"),
    ]


def test_single_notebook_path_is_not_treated_as_characters():
    from adf.jobs import serverless_job

    job = serverless_job("single-job", notebooks="who/01_staging")
    assert len(job.tasks) == 1
    assert job.tasks[0].notebook_path == "who/01_staging"
    assert job.tasks[0].after is None


@pytest.mark.parametrize("path", ["/Shared/notebook", "../notebook", "who/notebook.py", "who//notebook"])
def test_rejects_invalid_notebook_paths(path):
    from adf.jobs import notebook_task

    with pytest.raises(ValueError, match="relative.*without .py"):
        notebook_task("task", path)


def test_rejects_missing_task_dependency():
    from adf.jobs import notebook_task, serverless_job

    with pytest.raises(ValueError, match="depends on unknown task: missing"):
        serverless_job("bad-job", notebooks=(notebook_task("second", "who/second", after="missing"),))


def test_rejects_duplicate_and_cyclic_tasks():
    from adf.jobs import notebook_task, serverless_job

    with pytest.raises(ValueError, match="Duplicate task key"):
        serverless_job("duplicates", ("who/staging", "sales/staging"))
    with pytest.raises(ValueError, match="Cyclic task dependencies"):
        serverless_job(
            "cycle",
            (notebook_task("first", "who/first", after="second"), notebook_task("second", "who/second", after="first")),
        )


def test_discovers_jobs_and_checks_notebook_files(tmp_path):
    from adf.defs import discover_jobs
    from adf.jobs import serverless_job

    notebook_dir = tmp_path / "notebooks"
    (notebook_dir / "who").mkdir(parents=True)
    (notebook_dir / "who/01_staging.py").write_text("# Databricks notebook source\n")
    first = type("Pipeline", (), {"NAME": "one", "DATABRICKS_JOBS": (serverless_job("who", ("who/01_staging",)),)})

    assert [job.name for job in discover_jobs((first,), notebook_dir)] == ["who"]

    duplicate = type("Pipeline", (), {"NAME": "two", "DATABRICKS_JOBS": (serverless_job("who", ("who/01_staging",)),)})
    with pytest.raises(ValueError, match="Duplicate Databricks job name: who"):
        discover_jobs((first, duplicate), notebook_dir)

    missing = type("Pipeline", (), {"NAME": "missing", "DATABRICKS_JOBS": (serverless_job("missing", ("who/nope",)),)})
    with pytest.raises(ValueError, match="Notebook does not exist: who/nope"):
        discover_jobs((missing,), notebook_dir)


def test_repository_pipeline_declares_its_job_and_builds_with_generated_id(tmp_path):
    from adf.defs import discover_jobs, discover_pipelines
    from adf.deploy import build_pipelines
    from provisioner.config import load_settings

    settings = load_settings(tmp_path / ".env")
    pipelines = discover_pipelines()
    jobs = discover_jobs(pipelines, settings.notebook_source_dir)

    assert [job.name for job in jobs] == ["course-sales-etl"]
    built = build_pipelines(settings, {"course-sales-etl": "123"}, pipelines)
    sales = built["pl_sales_pipeline"]
    assert [activity.name for activity in sales.activities] == [
        "sales_start",
        "sales_wait",
        "sales_check",
        "copy_report_to_azure",
    ]
    assert sales.activities[0].body["job_id"] == 123
    assert built["pl_master_etl"].activities[1].depends_on[0].activity == "run_sales"


def teardown_module():
    for name in tuple(sys.modules):
        if name.startswith("defs_test_"):
            sys.modules.pop(name, None)
