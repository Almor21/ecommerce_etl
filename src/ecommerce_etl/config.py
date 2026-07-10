from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(PROJECT_ROOT / "data")

RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
QUARANTINE_DIR = DATA_DIR / "quarantine"
QUALITY_DIR = DATA_DIR / "quality"

WAREHOUSE_DB = DATA_DIR / "warehouse.duckdb"

DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

TABLES: tuple[str, ...] = (
    "customers", "products", "orders", "order_items", "payments", "reviews",
)
