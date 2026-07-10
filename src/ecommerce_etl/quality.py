from __future__ import annotations

from datetime import datetime

import polars as pl


class QualityReport:
    """Collects quality-check rows across tables and stages (long format)."""

    def __init__(self) -> None:
        self._rows: list[dict] = []

    def record(
        self,
        check_name: str,
        table: str,
        column: str,
        checked: int,
        failed: int,
        stage: str,
    ) -> None:
        """Append a single check row to the report."""
        self._rows.append(
            {
                "check_name": check_name,
                "table": table,
                "column": column,
                "records_checked": checked,
                "records_failed": failed,
                "pct_failed": round(100 * failed / checked, 2) if checked else 0.0,
                "stage": stage,
                "executed_at": datetime.now(),
            }
        )

    def null_check(self, df: pl.DataFrame, table: str, column: str, stage: str) -> None:
        """Record how many nulls a column has."""
        self.record("null_check", table, column, df.height, df[column].null_count(), stage)

    def duplicate_check(self, df: pl.DataFrame, table: str, key: str, stage: str) -> None:
        """Record how many duplicate keys a table has."""
        failed = df.height - df[key].n_unique()
        self.record("duplicate_check", table, key, df.height, failed, stage)

    def row_count(self, table: str, rows_in: int, rows_out: int, stage: str) -> None:
        """Record how many rows were dropped between two stages."""
        self.record("row_count", table, "*", rows_in, rows_in - rows_out, stage)

    def to_frame(self) -> pl.DataFrame:
        """Return the accumulated checks as a Polars DataFrame."""
        return pl.DataFrame(self._rows)
