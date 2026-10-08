"""Discover ADF pipeline definitions and their Databricks jobs."""

import importlib
import inspect
import pkgutil


def discover_pipelines(package_name="adf.defs"):
    """Import pl_*.py modules and order child pipelines before their parents."""
    package = importlib.import_module(package_name)
    modules = [
        importlib.import_module(f"{package_name}.{item.name}")
        for item in sorted(pkgutil.iter_modules(package.__path__), key=lambda item: item.name)
        if item.name.startswith("pl_") and not item.ispkg
    ]
    by_name = {}
    for module in modules:
        name = getattr(module, "NAME", None)
        if not isinstance(name, str) or not name.strip() or not callable(getattr(module, "build_pipeline", None)):
            raise ValueError(f"Pipeline module {module.__name__} must define NAME and build_pipeline")
        try:
            inspect.signature(module.build_pipeline).bind(None)
        except TypeError as error:
            raise ValueError(f"Pipeline {name}: build_pipeline must accept settings") from error
        if name in by_name:
            raise ValueError(f"Duplicate ADF pipeline name: {name}")
        by_name[name] = module

    ordered = []
    visiting = set()
    visited = set()

    def visit(name):
        if name in visiting:
            raise ValueError("Cyclic ADF pipeline dependencies")
        if name in visited:
            return
        module = by_name[name]
        visiting.add(name)
        for dependency in getattr(module, "PIPELINE_DEPENDENCIES", ()):
            if dependency not in by_name:
                raise ValueError(f"Pipeline {name} depends on unknown pipeline: {dependency}")
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(module)

    for name in by_name:
        visit(name)
    return tuple(ordered)
