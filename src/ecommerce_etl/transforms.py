from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from . import config


def strip_strings(df: pl.DataFrame, columns: Sequence[str]) -> pl.DataFrame:
    """Trim whitespace in the given text columns; blank strings become null."""
    exprs = []
    for col in columns:
        stripped = pl.col(col).str.strip_chars()
        exprs.append(
            pl.when(stripped.str.len_chars() == 0)
            .then(pl.lit(None, dtype=pl.String))
            .otherwise(stripped)
            .alias(col)
        )
    return df.with_columns(exprs)


def lowercase(df: pl.DataFrame, column: str) -> pl.DataFrame:
    """Lowercase a text column (nulls stay null)."""
    return df.with_columns(pl.col(column).str.to_lowercase().alias(column))


def uppercase(df: pl.DataFrame, column: str) -> pl.DataFrame:
    """Uppercase a text column (nulls stay null)."""
    return df.with_columns(pl.col(column).str.to_uppercase().alias(column))


def parse_datetime(
    df: pl.DataFrame, column: str, fmt: str = config.DEFAULT_DATETIME_FORMAT
) -> pl.DataFrame:
    """Parse a text column to datetime; unparseable values become null."""
    return df.with_columns(
        pl.col(column).str.to_datetime(fmt, strict=False).alias(column)
    )


def drop_null_keys(df: pl.DataFrame, key: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split rows on the primary key: (rows with key, rows missing key)."""
    kept = df.filter(pl.col(key).is_not_null())
    rejected = df.filter(pl.col(key).is_null())
    return kept, rejected


def deduplicate_by_key(
    df: pl.DataFrame, key: str, order_by: str, descending: bool = True
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Deduplicate by key keeping the latest row; returns (kept, removed)."""
    ordered = df.with_row_index("__row_id").sort(
        order_by, descending=descending, nulls_last=True
    )
    kept = ordered.unique(subset=[key], keep="first", maintain_order=True)
    removed = ordered.join(kept.select("__row_id"), on="__row_id", how="anti")
    return kept.drop("__row_id"), removed.drop("__row_id")
