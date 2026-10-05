"""Register children before the master that calls them."""

from adf.defs import pl_demo_pipeline, pl_master_etl, pl_sales_pipeline

PIPELINES = (pl_sales_pipeline, pl_demo_pipeline, pl_master_etl)
