"""Register complete pipeline definitions here in deployment order."""

from adf.defs import (
    pl_dependency_demo,
    pl_sales_job,
)

PIPELINES = (
    pl_sales_job,
    pl_dependency_demo,
)
