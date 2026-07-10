from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(PROJECT_ROOT / "data")

RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
QUARANTINE_DIR = DATA_DIR / "quarantine"
QUALITY_DIR = DATA_DIR / "quality"

WAREHOUSE_DB = PROJECT_ROOT / "warehouse.duckdb"

DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Categorías válidas de products, usadas por el accepted_values check.
# SUPOSICIÓN: esta lista se derivó explorando el dataset (ver notebook), porque es
# pequeño y fijo, así que se pueden enumerar todas fácilmente.
PRODUCT_CATEGORIES: frozenset[str] = frozenset({
    "automotive", "beauty", "books", "clothing", "electronics", "food",
    "furniture", "garden", "health", "home_appliances", "music",
    "office_supplies", "pet_shop", "sports", "toys",
})

# Estados válidos del ciclo de vida de un pedido (orders.status).
# SUPOSICIÓN: derivados de explorar el dataset (ver notebook). "unknown" y los
# blancos NO están aquí a propósito: se normalizan a null (= "sin estado conocido").
ORDER_STATUSES: frozenset[str] = frozenset({
    "delivered", "shipped", "processing", "canceled", "returned",
})
