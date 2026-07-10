from datetime import datetime

import polars as pl

from ecommerce_etl import transforms as T


def test_strip_strings_trims_and_nullifies_blanks():
    """Whitespace is trimmed and blank-only strings become null."""
    df = pl.DataFrame({"a": ["  hola ", "   ", "x", None]})
    out = T.strip_strings(df, ["a"])
    assert out["a"].to_list() == ["hola", None, "x", None]


def test_lowercase_keeps_nulls():
    """Values are lowercased and nulls are preserved."""
    df = pl.DataFrame({"email": ["Foo@Bar.COM", None]})
    out = T.lowercase(df, "email")
    assert out["email"].to_list() == ["foo@bar.com", None]


def test_uppercase_keeps_nulls():
    """Values are uppercased and nulls are preserved."""
    df = pl.DataFrame({"state": ["ba", "Mg", None]})
    out = T.uppercase(df, "state")
    assert out["state"].to_list() == ["BA", "MG", None]


def test_parse_datetime_permissive():
    """Valid dates parse; invalid text becomes null instead of raising."""
    df = pl.DataFrame({"created_at": ["2022-05-14 01:01:00", "no-es-fecha", None]})
    out = T.parse_datetime(df, "created_at")
    assert out.schema["created_at"] == pl.Datetime
    vals = out["created_at"].to_list()
    assert vals[0] == datetime(2022, 5, 14, 1, 1, 0)
    assert vals[1] is None
    assert vals[2] is None


def test_drop_null_keys_splits_kept_and_rejected():
    """Rows with a null key are sent to the rejected side."""
    df = pl.DataFrame({"customer_id": ["C1", None, "C2"], "x": [1, 2, 3]})
    kept, rejected = T.drop_null_keys(df, "customer_id")
    assert kept["customer_id"].to_list() == ["C1", "C2"]
    assert rejected["customer_id"].to_list() == [None]
    assert rejected["x"].to_list() == [2]


def test_deduplicate_by_key_keeps_latest_and_returns_removed():
    """Keeps the most recent row per key and returns the removed duplicates."""
    df = pl.DataFrame(
        {
            "customer_id": ["C1", "C1", "C2"],
            "created_at": [
                datetime(2021, 1, 1),
                datetime(2023, 1, 1),
                datetime(2022, 1, 1),
            ],
            "email": ["viejo@x.com", "nuevo@x.com", "c2@x.com"],
        }
    )
    kept, removed = T.deduplicate_by_key(df, key="customer_id", order_by="created_at")
    assert kept.height == 2
    c1 = kept.filter(pl.col("customer_id") == "C1")
    assert c1["email"].to_list() == ["nuevo@x.com"]
    assert removed.height == 1
    assert removed["email"].to_list() == ["viejo@x.com"]


def test_deduplicate_by_key_without_order_keeps_first():
    """With no order_by, the first row per key is kept and the rest returned."""
    df = pl.DataFrame({"product_id": ["P1", "P2", "P1"], "price": [10.0, 20.0, 99.0]})
    kept, removed = T.deduplicate_by_key(df, key="product_id")
    assert kept.height == 2
    assert kept.filter(pl.col("product_id") == "P1")["price"].to_list() == [10.0]
    assert removed["price"].to_list() == [99.0]


def test_cast_float_permissive():
    """Numeric text becomes float, non-numeric becomes null, and the fail count is returned."""
    df = pl.DataFrame({"price": ["10.5", "-3", "abc", None]})
    out, n_failed = T.cast_float(df, "price")
    assert out.schema["price"] == pl.Float64
    assert out["price"].to_list() == [10.5, -3.0, None, None]
    assert n_failed == 1  # only "abc" (the null was already null, not a cast failure)


def test_nullify_outside_range_low_bound():
    """Values below the low bound become null; returns how many were nulled."""
    df = pl.DataFrame({"price": [10.0, -5.0, 0.0, None]})
    out, n_out = T.nullify_outside_range(df, "price", low=0)
    assert out["price"].to_list() == [10.0, None, 0.0, None]
    assert n_out == 1


def test_nullify_outside_range_low_and_high():
    """Values outside the inclusive [low, high] range become null; returns the count."""
    df = pl.DataFrame({"score": [1, 0, 5, 6, 3, None]})
    out, n_out = T.nullify_outside_range(df, "score", low=1, high=5)
    assert out["score"].to_list() == [1, None, 5, None, 3, None]
    assert n_out == 2  # 0 and 6
