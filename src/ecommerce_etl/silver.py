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
    cast_int,
    deduplicate_by_key,
    drop_null_keys,
    lowercase,
    nullify_not_in_set,
    nullify_outside_range,
    parse_datetime,
    split_orphans,
    split_outside_range,
    strip_strings,
    uppercase,
)

CUSTOMERS_STRING_COLUMNS = ["customer_id", "customer_name", "email", "city", "state"]
CUSTOMERS_DESCRIPTIVE = ["customer_name", "email", "city", "state"]
PRODUCTS_STRING_COLUMNS = ["product_id", "product_name", "category"]
PRODUCTS_DESCRIPTIVE = ["product_name", "category", "price", "weight_kg"]
ORDERS_STRING_COLUMNS = ["order_id", "customer_id", "status"]
ORDERS_DESCRIPTIVE = ["status", "order_date", "approved_at", "delivered_at"]
ORDER_ITEMS_STRING_COLUMNS = ["item_id", "order_id", "product_id"]
ORDER_ITEMS_DESCRIPTIVE = ["quantity", "unit_price", "freight_value"]
PAYMENTS_STRING_COLUMNS = ["payment_id", "order_id", "payment_type"]
PAYMENTS_DESCRIPTIVE = ["payment_type", "installments", "amount"]
REVIEWS_STRING_COLUMNS = ["review_id", "order_id", "title", "comment"]
REVIEWS_DESCRIPTIVE = ["score", "title", "comment"]


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


def clean_order_items(
    df: pl.DataFrame,
    valid_order_ids: Collection[str],
    valid_product_ids: Collection[str],
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Clean the order_items table to Silver; returns (silver, rejected, metrics)."""
    df = strip_strings(df, ORDER_ITEMS_STRING_COLUMNS)
    df, cast_qty = cast_int(df, "quantity")
    df, cast_price = cast_float(df, "unit_price")
    df, cast_freight = cast_float(df, "freight_value")
    df, rejected_qty = split_outside_range(df, "quantity", low=1)
    df, rejected_price = drop_null_keys(df, "unit_price")
    df, rejected_order = split_orphans(df, "order_id", valid_order_ids)
    df, rejected_product = split_orphans(df, "product_id", valid_product_ids)
    df, rejected_null = drop_null_keys(df, "item_id")
    df, rejected_dup = deduplicate_by_key(df, "item_id")
    rejected = _quarantine(
        (rejected_qty, "invalid_quantity"),
        (rejected_price, "null_unit_price"),
        (rejected_order, "orphan_order"),
        (rejected_product, "orphan_product"),
        (rejected_null, "null_item_id"),
        (rejected_dup, "duplicate_item_id"),
    )
    metrics = {
        "cast_quantity": cast_qty,
        "cast_unit_price": cast_price,
        "cast_freight_value": cast_freight,
        "invalid_quantity": rejected_qty.height,
        "orphan_order": rejected_order.height,
        "orphan_product": rejected_product.height,
        "null_item_id": rejected_null.height,
        "duplicate_item_id": rejected_dup.height,
    }
    return df, rejected, metrics


def run_order_items() -> pl.DataFrame:
    """Build order_items Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "order_items.parquet")
    valid_order_ids = io.read_parquet(config.SILVER_DIR / "orders.parquet")["order_id"]
    valid_product_ids = io.read_parquet(config.SILVER_DIR / "products.parquet")["product_id"]
    silver, rejected, m = clean_order_items(bronze, valid_order_ids, valid_product_ids)
    schemas.OrderItemsSilver.validate(silver, lazy=True)

    report = QualityReport()
    report.null_counts(bronze, "order_items", ORDER_ITEMS_DESCRIPTIVE, "bronze")
    report.record("null_check", "order_items", "item_id", bronze.height, m["null_item_id"], "bronze")
    report.record("duplicate_check", "order_items", "item_id", bronze.height, m["duplicate_item_id"], "bronze")
    report.record("cast_check", "order_items", "quantity", bronze.height, m["cast_quantity"], "silver")
    report.record("cast_check", "order_items", "unit_price", bronze.height, m["cast_unit_price"], "silver")
    report.record("cast_check", "order_items", "freight_value", bronze.height, m["cast_freight_value"], "silver")
    report.record("range_check", "order_items", "quantity", bronze.height, m["invalid_quantity"], "silver")
    report.record("referential_integrity", "order_items", "order_id", bronze.height, m["orphan_order"], "silver")
    report.record("referential_integrity", "order_items", "product_id", bronze.height, m["orphan_product"], "silver")
    report.row_count("order_items", bronze.height, silver.height, "silver")

    io.write_parquet(silver, config.SILVER_DIR / "order_items.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "order_items.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "order_items.parquet")
    return silver


def clean_payments(
    df: pl.DataFrame, valid_order_ids: Collection[str]
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Clean the payments table to Silver; returns (silver, rejected, metrics)."""
    df = strip_strings(df, PAYMENTS_STRING_COLUMNS)
    df = lowercase(df, "payment_type")
    df, cast_installments = cast_int(df, "installments")
    df, cast_amount = cast_float(df, "amount")
    df, rejected_type = nullify_not_in_set(df, "payment_type", config.PAYMENT_TYPES)
    df, rejected_amount = split_outside_range(df, "amount", low=0)
    df, rejected_orphan = split_orphans(df, "order_id", valid_order_ids)
    df, rejected_null = drop_null_keys(df, "payment_id")
    df, rejected_dup = deduplicate_by_key(df, "payment_id")
    rejected = _quarantine(
        (rejected_type, "invalid_payment_type"),
        (rejected_amount, "invalid_amount"),
        (rejected_orphan, "orphan_order"),
        (rejected_null, "null_payment_id"),
        (rejected_dup, "duplicate_payment_id"),
    )
    metrics = {
        "cast_installments": cast_installments,
        "cast_amount": cast_amount,
        "invalid_payment_type": rejected_type.height,
        "invalid_amount": rejected_amount.height,
        "orphan_order": rejected_orphan.height,
        "null_payment_id": rejected_null.height,
        "duplicate_payment_id": rejected_dup.height,
    }
    return df, rejected, metrics


def run_payments() -> pl.DataFrame:
    """Build payments Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "payments.parquet")
    valid_order_ids = io.read_parquet(config.SILVER_DIR / "orders.parquet")["order_id"]
    silver, rejected, m = clean_payments(bronze, valid_order_ids)
    schemas.PaymentsSilver.validate(silver, lazy=True)

    report = QualityReport()
    report.null_counts(bronze, "payments", PAYMENTS_DESCRIPTIVE, "bronze")
    report.record("null_check", "payments", "payment_id", bronze.height, m["null_payment_id"], "bronze")
    report.record("duplicate_check", "payments", "payment_id", bronze.height, m["duplicate_payment_id"], "bronze")
    report.record("cast_check", "payments", "installments", bronze.height, m["cast_installments"], "silver")
    report.record("cast_check", "payments", "amount", bronze.height, m["cast_amount"], "silver")
    report.record("accepted_values", "payments", "payment_type", bronze.height, m["invalid_payment_type"], "silver")
    report.record("range_check", "payments", "amount", bronze.height, m["invalid_amount"], "silver")
    report.record("referential_integrity", "payments", "order_id", bronze.height, m["orphan_order"], "silver")
    report.row_count("payments", bronze.height, silver.height, "silver")

    io.write_parquet(silver, config.SILVER_DIR / "payments.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "payments.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "payments.parquet")
    return silver


def clean_reviews(
    df: pl.DataFrame, valid_order_ids: Collection[str]
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Clean the reviews table to Silver; returns (silver, rejected, metrics)."""
    df = strip_strings(df, REVIEWS_STRING_COLUMNS)
    df, cast_score = cast_int(df, "score")
    df, invalid_score = nullify_outside_range(df, "score", low=1, high=5)
    df = parse_datetime(df, "created_at")
    df, rejected_orphan = split_orphans(df, "order_id", valid_order_ids)
    df, rejected_null = drop_null_keys(df, "review_id")
    df, rejected_dup = deduplicate_by_key(df, "review_id", "created_at")
    rejected = _quarantine(
        (rejected_orphan, "orphan_order"),
        (rejected_null, "null_review_id"),
        (rejected_dup, "duplicate_review_id"),
    )
    metrics = {
        "cast_score": cast_score,
        "invalid_score": invalid_score,
        "orphan_order": rejected_orphan.height,
        "null_review_id": rejected_null.height,
        "duplicate_review_id": rejected_dup.height,
    }
    return df, rejected, metrics


def run_reviews() -> pl.DataFrame:
    """Build reviews Silver from Bronze; write silver, quarantine and quality."""
    bronze = io.read_parquet(config.BRONZE_DIR / "reviews.parquet")
    valid_order_ids = io.read_parquet(config.SILVER_DIR / "orders.parquet")["order_id"]
    silver, rejected, m = clean_reviews(bronze, valid_order_ids)
    schemas.ReviewsSilver.validate(silver, lazy=True)

    report = QualityReport()
    report.null_counts(bronze, "reviews", REVIEWS_DESCRIPTIVE, "bronze")
    report.record("null_check", "reviews", "review_id", bronze.height, m["null_review_id"], "bronze")
    report.record("duplicate_check", "reviews", "review_id", bronze.height, m["duplicate_review_id"], "bronze")
    report.record("cast_check", "reviews", "score", bronze.height, m["cast_score"], "silver")
    report.record("range_check", "reviews", "score", bronze.height, m["invalid_score"], "silver")
    report.record("referential_integrity", "reviews", "order_id", bronze.height, m["orphan_order"], "silver")
    report.row_count("reviews", bronze.height, silver.height, "silver")

    io.write_parquet(silver, config.SILVER_DIR / "reviews.parquet")
    io.write_parquet(rejected, config.QUARANTINE_DIR / "reviews.parquet")
    io.write_parquet(report.to_frame(), config.QUALITY_DIR / "reviews.parquet")
    return silver
