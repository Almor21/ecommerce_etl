from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

from . import config


def read_csv_raw(name: str) -> pl.DataFrame:
    return pl.read_csv(
        config.RAW_DIR / f"{name}.csv",
        infer_schema_length=0,
        null_values=[""],
    )


def write_parquet(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def read_parquet(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)
