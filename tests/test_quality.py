import polars as pl

from ecommerce_etl.quality import QualityReport


def test_null_check_counts_nulls_and_total():
    """null_check records the null count and the total rows checked."""
    df = pl.DataFrame({"email": ["a@x.com", None, None, "b@x.com"]})
    report = QualityReport()
    report.null_check(df, "customers", "email", "bronze")
    row = report.to_frame().row(0, named=True)
    assert row["check_name"] == "null_check"
    assert row["column"] == "email"
    assert row["records_checked"] == 4
    assert row["records_failed"] == 2
    assert row["pct_failed"] == 50.0
    assert row["stage"] == "bronze"


def test_duplicate_check_counts_duplicate_keys():
    """duplicate_check counts the rows beyond the unique keys."""
    df = pl.DataFrame({"customer_id": ["C1", "C1", "C2", "C3", "C3"]})
    report = QualityReport()
    report.duplicate_check(df, "customers", "customer_id", "bronze")
    row = report.to_frame().row(0, named=True)
    assert row["records_checked"] == 5
    assert row["records_failed"] == 2  # 5 filas - 3 ids únicos


def test_row_count_records_dropped_rows():
    """row_count records how many rows were dropped (in - out)."""
    report = QualityReport()
    report.row_count("customers", rows_in=5000, rows_out=4955, stage="silver")
    row = report.to_frame().row(0, named=True)
    assert row["check_name"] == "row_count"
    assert row["records_failed"] == 45
    assert row["pct_failed"] == 0.9


def test_accepted_values_check_counts_invalid():
    """Counts non-null values outside the allowed set; nulls are not counted."""
    df = pl.DataFrame({"category": ["sports", "bitcoin", None, "beauty"]})
    report = QualityReport()
    report.accepted_values_check(df, "products", "category", {"sports", "beauty"}, "silver")
    row = report.to_frame().row(0, named=True)
    assert row["check_name"] == "accepted_values"
    assert row["records_checked"] == 4
    assert row["records_failed"] == 1  # only "bitcoin"


def test_pct_failed_is_zero_when_nothing_checked():
    """pct_failed is 0.0 (no division by zero) when checked is 0."""
    report = QualityReport()
    report.record("null_check", "t", "c", checked=0, failed=0, stage="bronze")
    assert report.to_frame().row(0, named=True)["pct_failed"] == 0.0


def test_to_frame_accumulates_rows_with_long_format_schema():
    """The report accumulates one row per check with the expected columns."""
    report = QualityReport()
    report.record("a", "t", "c", 10, 1, "bronze")
    report.record("b", "t", "c", 10, 2, "silver")
    frame = report.to_frame()
    assert frame.height == 2
    assert set(frame.columns) == {
        "check_name", "table", "column", "records_checked",
        "records_failed", "pct_failed", "stage", "executed_at",
    }
