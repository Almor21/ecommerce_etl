from __future__ import annotations

from datetime import datetime

import pandera.polars as pa

from .config import ORDER_STATUSES, PRODUCT_CATEGORIES


class CustomersSilver(pa.DataFrameModel):
    """Contract for the cleaned customers table."""

    customer_id: str = pa.Field(nullable=False, unique=True)
    customer_name: str = pa.Field(nullable=True)
    email: str = pa.Field(nullable=True)
    city: str = pa.Field(nullable=True)
    state: str = pa.Field(nullable=True)
    created_at: datetime = pa.Field(nullable=False)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True


class ProductsSilver(pa.DataFrameModel):
    """Contract for the cleaned products table."""

    product_id: str = pa.Field(nullable=False, unique=True)
    product_name: str = pa.Field(nullable=True)
    category: str = pa.Field(nullable=True, isin=list(PRODUCT_CATEGORIES))
    price: float = pa.Field(nullable=True, ge=0)
    weight_kg: float = pa.Field(nullable=True, ge=0)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True


class OrdersSilver(pa.DataFrameModel):
    """Contract for the cleaned orders table."""

    order_id: str = pa.Field(nullable=False, unique=True)
    customer_id: str = pa.Field(nullable=False)  # FK to customers (not unique)
    status: str = pa.Field(nullable=True, isin=list(ORDER_STATUSES))
    order_date: datetime = pa.Field(nullable=True)
    approved_at: datetime = pa.Field(nullable=True)
    delivered_at: datetime = pa.Field(nullable=True)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True
