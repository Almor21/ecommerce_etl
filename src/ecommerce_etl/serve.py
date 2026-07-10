from __future__ import annotations

from pathlib import Path

import duckdb

from . import config


def _load(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> None:
    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet('{path}')")


def run() -> None:
    """Rebuild warehouse.duckdb from the Silver, Gold, quality and quarantine parquets."""
    config.WAREHOUSE_DB.unlink(missing_ok=True)
    con = duckdb.connect(str(config.WAREHOUSE_DB))
    try:
        for t in config.TABLES:
            _load(con, f"silver_{t}", config.SILVER_DIR / f"{t}.parquet")
            _load(con, f"quarantine_{t}", config.QUARANTINE_DIR / f"{t}.parquet")
        for path in sorted(config.GOLD_DIR.glob("*.parquet")):
            _load(con, path.stem, path)
            
        con.execute(
            "CREATE OR REPLACE TABLE quality_checks AS "
            f"SELECT * FROM read_parquet('{config.QUALITY_DIR}/*.parquet')"
        )
    finally:
        con.close()
