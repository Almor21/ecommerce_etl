from __future__ import annotations

from collections.abc import Collection, Sequence

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


def cast_float(df: pl.DataFrame, column: str) -> tuple[pl.DataFrame, int]:
    """Cast a text column to float; returns (df, count of values that failed to cast)."""
    casted = pl.col(column).cast(pl.Float64, strict=False)
    df = df.with_columns(
        casted.alias(column),
        (pl.col(column).is_not_null() & casted.is_null()).alias("__cast_failed"),
    )
    n_failed = int(df.get_column("__cast_failed").sum())
    return df.drop("__cast_failed"), n_failed


def nullify_outside_range(
    df: pl.DataFrame,
    column: str,
    low: float | None = None,
    high: float | None = None,
) -> tuple[pl.DataFrame, int]:
    """Null values outside the inclusive [low, high] range; returns (df, count nulled)."""
    col = pl.col(column)
    out_of_range = pl.lit(False)
    if low is not None:
        out_of_range = out_of_range | (col < low)
    if high is not None:
        out_of_range = out_of_range | (col > high)
    df = df.with_columns(
        pl.when(out_of_range).then(None).otherwise(col).alias(column),
        out_of_range.fill_null(False).alias("__out_of_range"),
    )
    n_out = int(df.get_column("__out_of_range").sum())
    return df.drop("__out_of_range"), n_out


def nullify_not_in_set(
    df: pl.DataFrame, column: str, allowed: Collection[str]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Null values not in `allowed`; returns (df, rejected).

    The row is kept (only the bad value is nulled), and a copy of each bad row —
    with its original value — is returned for audit. Genuine nulls are left as-is.
    """
    invalid = pl.col(column).is_not_null() & ~pl.col(column).is_in(list(allowed))
    rejected = df.filter(invalid)  # original rows, before nulling, for the audit trail
    df = df.with_columns(
        pl.when(invalid).then(None).otherwise(pl.col(column)).alias(column)
    )
    return df, rejected


def split_orphans(
    df: pl.DataFrame, fk_column: str, valid_keys: Collection[str]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split rows by referential integrity: (fk present in valid_keys, orphans).

    A null FK is kept — a missing reference is not a broken one.
    """
    is_orphan = pl.col(fk_column).is_not_null() & ~pl.col(fk_column).is_in(list(valid_keys))
    return df.filter(~is_orphan), df.filter(is_orphan)


def drop_null_keys(df: pl.DataFrame, key: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split rows on the primary key: (rows with key, rows missing key)."""
    kept = df.filter(pl.col(key).is_not_null())
    rejected = df.filter(pl.col(key).is_null())
    return kept, rejected


def deduplicate_by_key(
    df: pl.DataFrame, key: str, order_by: str | None = None, descending: bool = True
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Deduplicate by key keeping the latest row by `order_by`, or the first row
    when `order_by` is None; returns (kept, removed)."""
    indexed = df.with_row_index("__row_id")
    ordered = (
        indexed
        if order_by is None
        else indexed.sort(order_by, descending=descending, nulls_last=True)
    )
    kept = ordered.unique(subset=[key], keep="first", maintain_order=True)
    removed = ordered.join(kept.select("__row_id"), on="__row_id", how="anti")
    return kept.drop("__row_id"), removed.drop("__row_id")
