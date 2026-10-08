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
def build_pipeline(settings): pass
""",
            "pl_child.py": """
NAME = "child"
def build_pipeline(settings): pass
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
                "pl_one.py": 'NAME = "same"\ndef build_pipeline(settings): pass\n',
                "pl_two.py": 'NAME = "same"\ndef build_pipeline(settings): pass\n',
            },
            "Duplicate ADF pipeline name: same",
        ),
        (
            {"pl_one.py": 'NAME = "one"\nPIPELINE_DEPENDENCIES = ("missing",)\ndef build_pipeline(settings): pass\n'},
            "Pipeline one depends on unknown pipeline: missing",
        ),
        (
            {
                "pl_one.py": 'NAME = "one"\nPIPELINE_DEPENDENCIES = ("two",)\ndef build_pipeline(settings): pass\n',
                "pl_two.py": 'NAME = "two"\nPIPELINE_DEPENDENCIES = ("one",)\ndef build_pipeline(settings): pass\n',
            },
            "Cyclic ADF pipeline dependencies",
        ),
        (
            {"pl_old.py": 'NAME = "old"\ndef build_pipeline(settings, job_ids): pass\n'},
            "must accept settings",
        ),
    ],
)
def test_rejects_invalid_pipeline_discovery(tmp_path, monkeypatch, files, message):
    from adf.defs import discover_pipelines

    package = _package(tmp_path, monkeypatch, files)
    with pytest.raises(ValueError, match=message):
        discover_pipelines(package)


def teardown_module():
    for name in tuple(sys.modules):
        if name.startswith("defs_test_"):
            sys.modules.pop(name, None)
