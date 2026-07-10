from __future__ import annotations

from datetime import datetime

import polars as pl

from . import config, io


def ingest(name: str) -> pl.DataFrame:
    """Read a raw CSV as text and add the ingestion metadata columns."""
    return io.read_csv_raw(name).with_columns(
        pl.lit(f"{name}.csv").alias("_source_file"),
        pl.lit(datetime.now()).alias("_ingested_at"),
    )


def run(name: str) -> pl.DataFrame:
    """Ingest one raw table to Bronze and write its Parquet."""
    bronze = ingest(name)
    io.write_parquet(bronze, config.BRONZE_DIR / f"{name}.parquet")
    return bronze
