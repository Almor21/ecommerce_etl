from __future__ import annotations

from datetime import datetime

import pandera.polars as pa

from .config import ORDER_STATUSES, PAYMENT_TYPES, PRODUCT_CATEGORIES


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
    customer_id: str = pa.Field(nullable=False)
    status: str = pa.Field(nullable=True, isin=list(ORDER_STATUSES))
    order_date: datetime = pa.Field(nullable=True)
    approved_at: datetime = pa.Field(nullable=True)
    delivered_at: datetime = pa.Field(nullable=True)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True


class OrderItemsSilver(pa.DataFrameModel):
    """Contract for the cleaned order_items table."""

    item_id: str = pa.Field(nullable=False, unique=True)
    order_id: str = pa.Field(nullable=False)
    product_id: str = pa.Field(nullable=False)
    quantity: int = pa.Field(nullable=False, gt=0)
    unit_price: float = pa.Field(nullable=False, ge=0)
    freight_value: float = pa.Field(nullable=True, ge=0)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True


class PaymentsSilver(pa.DataFrameModel):
    """Contract for the cleaned payments table."""

    payment_id: str = pa.Field(nullable=False, unique=True)
    order_id: str = pa.Field(nullable=False)
    payment_type: str = pa.Field(nullable=True, isin=list(PAYMENT_TYPES))
    installments: int = pa.Field(nullable=True)
    amount: float = pa.Field(nullable=False, ge=0)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True


class ReviewsSilver(pa.DataFrameModel):
    """Contract for the cleaned reviews table."""

    review_id: str = pa.Field(nullable=False, unique=True)
    order_id: str = pa.Field(nullable=False)
    score: int = pa.Field(nullable=True, ge=1, le=5)
    title: str = pa.Field(nullable=True)
    comment: str = pa.Field(nullable=True)
    created_at: datetime = pa.Field(nullable=False)
    source_file: str = pa.Field(alias="_source_file", nullable=False)
    ingested_at: datetime = pa.Field(alias="_ingested_at", nullable=False)

    class Config:
        coerce = False
        strict = True
