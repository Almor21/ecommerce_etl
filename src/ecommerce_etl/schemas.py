from __future__ import annotations

from datetime import datetime

import pandera.polars as pa


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
