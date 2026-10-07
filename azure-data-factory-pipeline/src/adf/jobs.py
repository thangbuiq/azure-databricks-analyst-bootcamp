"""Small declarations for Databricks jobs owned by ADF pipeline definitions."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class NotebookTask:
    task_key: str
    notebook_path: str
    after: str | None = None


@dataclass(frozen=True)
class ServerlessJob:
    name: str
    tasks: tuple[NotebookTask, ...]


def notebook_task(task_key: str, notebook_path: str, after: str | None = None) -> NotebookTask:
    """Declare one workspace notebook task using a path relative to the deployed notebook folder."""
    path = PurePosixPath(notebook_path)
    if (
        not notebook_path
        or path.is_absolute()
        or path.as_posix() != notebook_path
        or ".." in path.parts
        or path.suffix == ".py"
    ):
        raise ValueError(f"Notebook path must be relative and written without .py: {notebook_path}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_key):
        raise ValueError(f"Invalid Databricks task key: {task_key}")
    return NotebookTask(task_key=task_key, notebook_path=notebook_path, after=after)


def serverless_job(name: str, notebooks) -> ServerlessJob:
    """Declare a serverless job; plain notebook paths run sequentially in the supplied order."""
    if isinstance(notebooks, str):
        notebooks = (notebooks,)
    tasks = []
    previous = None
    for item in notebooks:
        task = notebook_task(PurePosixPath(item).name, item, after=previous) if isinstance(item, str) else item
        if not isinstance(task, NotebookTask):
            raise TypeError("Job notebooks must be paths or NotebookTask values")
        tasks.append(task)
        previous = task.task_key
    if not name or not tasks:
        raise ValueError("A Databricks job requires a name and at least one notebook")

    keys = [task.task_key for task in tasks]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate task key in Databricks job {name}")
    known = set(keys)
    for task in tasks:
        if task.after and task.after not in known:
            raise ValueError(f"Task {task.task_key} depends on unknown task: {task.after}")

    dependencies = {task.task_key: task.after for task in tasks}
    for task in tasks:
        seen = set()
        current = task.task_key
        while current:
            if current in seen:
                raise ValueError(f"Cyclic task dependencies in Databricks job {name}")
            seen.add(current)
            current = dependencies[current]
    return ServerlessJob(name=name, tasks=tuple(tasks))
