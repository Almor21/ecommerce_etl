from __future__ import annotations

import polars as pl

from . import config, io, schemas
from .quality import QualityReport
from .transforms import (
    deduplicate_by_key,
    drop_null_keys,
    lowercase,
    parse_datetime,
    strip_strings,
    uppercase,
)

CUSTOMERS_STRING_COLUMNS = ["customer_id", "customer_name", "email", "city", "state"]


def clean_customers(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Clean the customers table to Silver; returns (silver, rejected)."""
    df = parse_datetime(df, "created_at")
    df = strip_strings(df, CUSTOMERS_STRING_COLUMNS)
    df = lowercase(df, "email")
    df = uppercase(df, "state")
    df, rejected_null = drop_null_keys(df, "customer_id")
    df, rejected_dup = deduplicate_by_key(df, "customer_id", "created_at")
    rejected = pl.concat(
        [
            rejected_null.with_columns(pl.lit("null_customer_id").alias("reject_reason")),
            rejected_dup.with_columns(pl.lit("duplicate_customer_id").alias("reject_reason")),
        ],
        how="diagonal",
    )
    return df, rejected


def _record_customers_quality(
    report: QualityReport, bronze: pl.DataFrame, silver: pl.DataFrame
) -> None:
    """Record the customers checks: bronze portrait + silver verification."""
    # bronze: how many nulls/dups arrived
    for col in CUSTOMERS_STRING_COLUMNS:
        report.null_check(bronze, "customers", col, "bronze")
    report.duplicate_check(bronze, "customers", "customer_id", "bronze")
    
    # silver: verify the cleaning acted
    report.null_check(silver, "customers", "customer_id", "silver")
    report.duplicate_check(silver, "customers", "customer_id", "silver")
    report.row_count("customers", bronze.height, silver.height, "silver")


def run_customers() -> pl.DataFrame:
    """Build customers Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "customers.parquet")
    silver, rejected = clean_customers(bronze)

    schemas.CustomersSilver.validate(silver, lazy=True)

    report = QualityReport()
    _record_customers_quality(report, bronze, silver)

    io.write_parquet(silver, config.SILVER_DIR / "customers.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "customers.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "customers.parquet")
    return silver
