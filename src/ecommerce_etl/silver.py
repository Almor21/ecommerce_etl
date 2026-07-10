"""Silver layer: clean and validate Bronze tables, capturing quality and quarantine.

Per-table cleaning composes the generic primitives from `transforms`. The value
transforms return the metric they produced (e.g. how many values failed to cast),
so the quality checks reuse those counts instead of scanning the data again. The
"did the cleaning work?" verification is the Pandera contract's job (it raises),
not the quality table's.
"""

from __future__ import annotations

from collections.abc import Collection

import polars as pl

from . import config, io, schemas
from .quality import QualityReport
from .transforms import (
    cast_float,
    deduplicate_by_key,
    drop_null_keys,
    lowercase,
    nullify_not_in_set,
    nullify_outside_range,
    parse_datetime,
    split_orphans,
    strip_strings,
    uppercase,
)

CUSTOMERS_STRING_COLUMNS = ["customer_id", "customer_name", "email", "city", "state"]
CUSTOMERS_DESCRIPTIVE = ["customer_name", "email", "city", "state"]
PRODUCTS_STRING_COLUMNS = ["product_id", "product_name", "category"]
PRODUCTS_DESCRIPTIVE = ["product_name", "category", "price", "weight_kg"]
ORDERS_STRING_COLUMNS = ["order_id", "customer_id", "status"]
ORDERS_DESCRIPTIVE = ["status", "order_date", "approved_at", "delivered_at"]


def _quarantine(*frames_with_reason: tuple[pl.DataFrame, str]) -> pl.DataFrame:
    """Concat rejected frames, each tagged with its reject_reason."""
    return pl.concat(
        [
            frame.with_columns(pl.lit(reason).alias("reject_reason"))
            for frame, reason in frames_with_reason
        ],
        how="diagonal",
    )


def clean_customers(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Clean the customers table to Silver; returns (silver, rejected, metrics)."""
    df = parse_datetime(df, "created_at")
    df = strip_strings(df, CUSTOMERS_STRING_COLUMNS)
    df = lowercase(df, "email")
    df = uppercase(df, "state")
    df, rejected_null = drop_null_keys(df, "customer_id")
    df, rejected_dup = deduplicate_by_key(df, "customer_id", "created_at")
    rejected = _quarantine(
        (rejected_null, "null_customer_id"), (rejected_dup, "duplicate_customer_id")
    )
    metrics = {
        "null_customer_id": rejected_null.height,
        "duplicate_customer_id": rejected_dup.height,
    }
    return df, rejected, metrics


def clean_products(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Clean the products table to Silver; returns (silver, rejected, metrics)."""
    df = strip_strings(df, PRODUCTS_STRING_COLUMNS)
    df = lowercase(df, "category")
    df, cast_price = cast_float(df, "price")
    df, cast_weight = cast_float(df, "weight_kg")
    df, neg_price = nullify_outside_range(df, "price", low=0)
    df, rejected_cat = nullify_not_in_set(df, "category", config.PRODUCT_CATEGORIES)
    df, rejected_null = drop_null_keys(df, "product_id")
    df, rejected_dup = deduplicate_by_key(df, "product_id")
    rejected = _quarantine(
        (rejected_null, "null_product_id"),
        (rejected_dup, "duplicate_product_id"),
        (rejected_cat, "invalid_category"),
    )
    metrics = {
        "cast_price": cast_price,
        "cast_weight": cast_weight,
        "range_price": neg_price,
        "invalid_category": rejected_cat.height,
        "null_product_id": rejected_null.height,
        "duplicate_product_id": rejected_dup.height,
    }
    return df, rejected, metrics


def run_customers() -> pl.DataFrame:
    """Build customers Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "customers.parquet")
    silver, rejected, m = clean_customers(bronze)
    schemas.CustomersSilver.validate(silver, lazy=True)

    report = QualityReport()
    report.null_counts(bronze, "customers", CUSTOMERS_DESCRIPTIVE, "bronze")
    report.record("null_check", "customers", "customer_id", bronze.height, m["null_customer_id"], "bronze")
    report.record("duplicate_check", "customers", "customer_id", bronze.height, m["duplicate_customer_id"], "bronze")
    report.row_count("customers", bronze.height, silver.height, "silver")

    io.write_parquet(silver, config.SILVER_DIR / "customers.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "customers.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "customers.parquet")
    return silver


def run_products() -> pl.DataFrame:
    """Build products Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "products.parquet")
    silver, rejected, m = clean_products(bronze)
    schemas.ProductsSilver.validate(silver, lazy=True)

    report = QualityReport()
    report.null_counts(bronze, "products", PRODUCTS_DESCRIPTIVE, "bronze")
    report.record("null_check", "products", "product_id", bronze.height, m["null_product_id"], "bronze")
    report.record("duplicate_check", "products", "product_id", bronze.height, m["duplicate_product_id"], "bronze")
    report.record("cast_check", "products", "price", bronze.height, m["cast_price"], "silver")
    report.record("cast_check", "products", "weight_kg", bronze.height, m["cast_weight"], "silver")
    report.record("range_check", "products", "price", bronze.height, m["range_price"], "silver")
    report.record("accepted_values", "products", "category", bronze.height, m["invalid_category"], "silver")
    report.row_count("products", bronze.height, silver.height, "silver")

    io.write_parquet(silver, config.SILVER_DIR / "products.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "products.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "products.parquet")
    return silver


def clean_orders(
    df: pl.DataFrame, valid_customer_ids: Collection[str]
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Clean the orders table to Silver; returns (silver, rejected, metrics)."""
    df = strip_strings(df, ORDERS_STRING_COLUMNS)
    df = lowercase(df, "status")
    df = parse_datetime(df, "order_date")
    df = parse_datetime(df, "approved_at")
    df = parse_datetime(df, "delivered_at")
    df, rejected_status = nullify_not_in_set(df, "status", config.ORDER_STATUSES)
    df, rejected_orphan = split_orphans(df, "customer_id", valid_customer_ids)
    df, rejected_null = drop_null_keys(df, "order_id")
    df, rejected_dup = deduplicate_by_key(df, "order_id", "order_date")
    rejected = _quarantine(
        (rejected_status, "invalid_status"),
        (rejected_orphan, "orphan_customer"),
        (rejected_null, "null_order_id"),
        (rejected_dup, "duplicate_order_id"),
    )
    metrics = {
        "invalid_status": rejected_status.height,
        "orphan_customer": rejected_orphan.height,
        "null_order_id": rejected_null.height,
        "duplicate_order_id": rejected_dup.height,
    }
    return df, rejected, metrics


def run_orders() -> pl.DataFrame:
    """Build orders Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "orders.parquet")
    valid_customer_ids = io.read_parquet(config.SILVER_DIR / "customers.parquet")["customer_id"]
    silver, rejected, m = clean_orders(bronze, valid_customer_ids)
    schemas.OrdersSilver.validate(silver, lazy=True)

    report = QualityReport()
    report.null_counts(bronze, "orders", ORDERS_DESCRIPTIVE, "bronze")
    report.record("null_check", "orders", "order_id", bronze.height, m["null_order_id"], "bronze")
    report.record("duplicate_check", "orders", "order_id", bronze.height, m["duplicate_order_id"], "bronze")
    report.record("accepted_values", "orders", "status", bronze.height, m["invalid_status"], "silver")
    report.record("referential_integrity", "orders", "customer_id", bronze.height, m["orphan_customer"], "silver")
    report.row_count("orders", bronze.height, silver.height, "silver")

    io.write_parquet(silver, config.SILVER_DIR / "orders.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "orders.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "orders.parquet")
    return silver
