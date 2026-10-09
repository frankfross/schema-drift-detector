"""Tests for schema inference."""

from drift.infer import infer_type, parse_value, snapshot_csv


def test_infer_basic_types():
    assert infer_type(["1", "2", "3"]) == "int"
    assert infer_type(["1.5", "2"]) == "float"
    assert infer_type(["true", "FALSE", "yes"]) == "bool"
    assert infer_type(["2026-01-02", "2026-12-31"]) == "date"
    assert infer_type(["2026-01-02T10:00:00"]) == "datetime"
    assert infer_type(["hello", "42"]) == "str"


def test_infer_narrowest_fit():
    # mixed int/float widens to float; anything else falls back to str
    assert infer_type(["1", "2.5"]) == "float"
    assert infer_type(["1", "abc"]) == "str"
    assert infer_type(["2026-13-99"]) == "str"  # invalid date -> str


def test_infer_ignores_nulls():
    assert infer_type(["1", "", "3"]) == "int"
    assert infer_type(["", ""]) == "str"  # all-null: unknown


def test_parse_value_nulls_ok():
    assert parse_value("", "int")
    assert parse_value("  ", "date")


def test_snapshot_examples(tmp_path):
    schema = snapshot_csv("examples/orders_v1.csv")
    assert schema["row_count"] == 5
    cols = schema["columns"]
    assert cols["order_id"]["type"] == "int"
    assert cols["amount_usd"]["type"] == "float"
    assert cols["created_date"]["type"] == "date"
    assert cols["is_refund"]["type"] == "bool"
    assert cols["order_id"]["nullable"] is False
