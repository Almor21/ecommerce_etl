from __future__ import annotations

from pathlib import Path

import duckdb

from . import config

SCHEMAS = ("silver", "quarantine", "gold", "quality")


def _load(con: duckdb.DuckDBPyConnection, table: str, source: str | Path) -> None:
    """Create `table` (schema-qualified) from a parquet path or glob."""
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{source}')")


def run() -> None:
    """Rebuild warehouse.duckdb with one schema per medallion concern."""
    config.WAREHOUSE_DB.unlink(missing_ok=True)
    con = duckdb.connect(str(config.WAREHOUSE_DB))
    try:
        for schema in SCHEMAS:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        for t in config.TABLES:
            _load(con, f"silver.{t}", config.SILVER_DIR / f"{t}.parquet")
            _load(con, f"quarantine.{t}", config.QUARANTINE_DIR / f"{t}.parquet")

        for path in sorted(config.GOLD_DIR.glob("*.parquet")):
            _load(con, f"gold.{path.stem.removeprefix('gold_')}", path)

        _load(con, "quality.checks", f"{config.QUALITY_DIR}/*.parquet")
    finally:
        con.close()
