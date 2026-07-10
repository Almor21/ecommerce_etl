from __future__ import annotations

import polars as pl

from . import config, io
from .enums import OrderStatus


def _load_silver() -> dict[str, pl.DataFrame]:
    """Read every Silver table into a dict keyed by table name."""
    return {t: io.read_parquet(config.SILVER_DIR / f"{t}.parquet") for t in config.TABLES}


def _sales_lines(orders: pl.DataFrame, order_items: pl.DataFrame) -> pl.DataFrame:
    """order_items enriched with order status/date/customer"""
    return (
        order_items.join(
            orders.select("order_id", "customer_id", "status", "order_date"),
            on="order_id",
            how="inner",
        )
        .filter(pl.col("status") != OrderStatus.CANCELED)
        .with_columns((pl.col("quantity") * pl.col("unit_price")).alias("line_revenue"))
    )


def build_sales_by_state(
    orders: pl.DataFrame, order_items: pl.DataFrame, customers: pl.DataFrame
) -> pl.DataFrame:
    """Revenue, number of orders and average ticket by customer state."""
    return (
        _sales_lines(orders, order_items)
        .join(customers.select("customer_id", "state"), on="customer_id", how="inner")
        .with_columns(pl.col("state").fill_null("UNKNOWN"))
        .group_by("state")
        .agg(
            pl.col("line_revenue").sum().round(2).alias("revenue"),
            pl.col("order_id").n_unique().alias("num_orders"),
        )
        .with_columns((pl.col("revenue") / pl.col("num_orders")).round(2).alias("avg_ticket"))
        .sort("revenue", descending=True)
    )


def build_product_performance(
    orders: pl.DataFrame,
    order_items: pl.DataFrame,
    products: pl.DataFrame,
    reviews: pl.DataFrame,
) -> pl.DataFrame:
    """Per product: units sold, revenue, distinct orders, avg review score, return rate."""
    lines = order_items.join(
        orders.select("order_id", "status"), on="order_id", how="inner"
    ).with_columns((pl.col("quantity") * pl.col("unit_price")).alias("line_revenue"))

    sales = (
        lines.filter(pl.col("status") != OrderStatus.CANCELED)
        .group_by("product_id")
        .agg(
            pl.col("quantity").sum().alias("units_sold"),
            pl.col("line_revenue").sum().round(2).alias("revenue"),
            pl.col("order_id").n_unique().alias("num_orders"),
        )
    )
    returns = (
        lines.group_by("product_id")
        .agg(
            pl.col("order_id").n_unique().alias("_total"),
            pl.col("order_id").filter(pl.col("status") == OrderStatus.RETURNED).n_unique().alias("_returned"),
        )
        .with_columns((pl.col("_returned") / pl.col("_total") * 100).round(2).alias("return_rate"))
    )
    review_score = (
        order_items.select("order_id", "product_id")
        .join(reviews.select("order_id", "score"), on="order_id", how="inner")
        .filter(pl.col("score").is_not_null())
        .group_by("product_id")
        .agg(pl.col("score").mean().round(2).alias("avg_review_score"))
    )
    return (
        products.select("product_id", "product_name", "category")
        .join(sales, on="product_id", how="inner")
        .join(returns.select("product_id", "return_rate"), on="product_id", how="left")
        .join(review_score, on="product_id", how="left")
        .sort("revenue", descending=True)
    )


def build_customer_segments(
    orders: pl.DataFrame, order_items: pl.DataFrame, customers: pl.DataFrame
) -> pl.DataFrame:
    """Simplified RFM: recency (days since last order), frequency (orders), monetary (spend)."""
    reference_date = orders.select(pl.col("order_date").max()).item()
    rfm = (
        _sales_lines(orders, order_items)
        .filter(pl.col("order_date").is_not_null())
        .group_by("customer_id")
        .agg(
            pl.col("order_date").max().alias("_last_order"),
            pl.col("order_id").n_unique().alias("frequency"),
            pl.col("line_revenue").sum().round(2).alias("monetary"),
        )
        .with_columns(
            (pl.lit(reference_date) - pl.col("_last_order")).dt.total_days().alias("recency_days")
        )
    )
    rfm = rfm.with_columns(
        pl.col("recency_days").qcut(4, labels=["4", "3", "2", "1"], allow_duplicates=True)
        .cast(pl.String).cast(pl.Int8).alias("R"),
        pl.col("frequency").qcut(4, labels=["1", "2", "3", "4"], allow_duplicates=True)
        .cast(pl.String).cast(pl.Int8).alias("F"),
        pl.col("monetary").qcut(4, labels=["1", "2", "3", "4"], allow_duplicates=True)
        .cast(pl.String).cast(pl.Int8).alias("M"),
    ).with_columns((pl.col("R") + pl.col("F") + pl.col("M")).alias("rfm_score"))
    rfm = rfm.with_columns(
        pl.when(pl.col("rfm_score") >= 10).then(pl.lit("Champions"))
        .when(pl.col("rfm_score") >= 8).then(pl.lit("Loyal"))
        .when(pl.col("rfm_score") >= 6).then(pl.lit("Potential"))
        .when(pl.col("rfm_score") >= 4).then(pl.lit("At Risk"))
        .otherwise(pl.lit("Lost"))
        .alias("segment")
    )
    return (
        customers.select("customer_id", "customer_name", "state")
        .join(rfm, on="customer_id", how="inner")
        .select(
            "customer_id", "customer_name", "state",
            "recency_days", "frequency", "monetary", "R", "F", "M", "rfm_score", "segment",
        )
        .sort("monetary", descending=True)
    )


def build_monthly_kpis(
    orders: pl.DataFrame, order_items: pl.DataFrame, reviews: pl.DataFrame
) -> pl.DataFrame:
    """Per month: revenue, orders, cancellations, cancellation rate and avg review score."""
    revenue = (
        _sales_lines(orders, order_items)
        .filter(pl.col("order_date").is_not_null())
        .with_columns(pl.col("order_date").dt.truncate("1mo").alias("month"))
        .group_by("month")
        .agg(
            pl.col("line_revenue").sum().round(2).alias("revenue"),
            pl.col("order_id").n_unique().alias("num_orders"),
        )
    )
    order_stats = (
        orders.filter(pl.col("order_date").is_not_null())
        .with_columns(pl.col("order_date").dt.truncate("1mo").alias("month"))
        .group_by("month")
        .agg(
            pl.col("order_id").n_unique().alias("total_orders"),
            (pl.col("status") == OrderStatus.CANCELED).sum().alias("num_canceled"),
        )
    )
    review_stats = (
        reviews.join(orders.select("order_id", "order_date"), on="order_id", how="inner")
        .filter(pl.col("order_date").is_not_null() & pl.col("score").is_not_null())
        .with_columns(pl.col("order_date").dt.truncate("1mo").alias("month"))
        .group_by("month")
        .agg(pl.col("score").mean().round(2).alias("avg_review_score"))
    )
    return (
        order_stats.join(revenue, on="month", how="left")
        .join(review_stats, on="month", how="left")
        .with_columns(
            (pl.col("num_canceled") / pl.col("total_orders") * 100).round(2).alias("cancellation_rate")
        )
        .sort("month")
    )


def run() -> dict[str, pl.DataFrame]:
    """Build every Gold table from the Silver parquets and write them to data/gold/."""
    s = _load_silver()
    tables = {
        "gold_sales_by_state": build_sales_by_state(s["orders"], s["order_items"], s["customers"]),
        "gold_product_performance": build_product_performance(
            s["orders"], s["order_items"], s["products"], s["reviews"]
        ),
        "gold_customer_segments": build_customer_segments(s["orders"], s["order_items"], s["customers"]),
        "gold_monthly_kpis": build_monthly_kpis(s["orders"], s["order_items"], s["reviews"]),
    }
    for name, df in tables.items():
        io.write_parquet(df, config.GOLD_DIR / f"{name}.parquet")
    return tables
