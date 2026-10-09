"""Tests for drift detection."""

from drift.detect import detect_drift


def _schema(**cols):
    return {"row_count": 5, "columns": cols}


def _col(t, nullable=False):
    return {"type": t, "nullable": nullable, "null_fraction": 0.0}


def test_no_drift():
    base = _schema(a=_col("int"), b=_col("str"))
    report = detect_drift(base, _schema(a=_col("int"), b=_col("str")))
    assert report["findings"] == []
    assert report["summary"] == {"errors": 0, "warnings": 0, "breaking": False}


def test_added_removed():
    base = _schema(a=_col("int"), old=_col("str"))
    cur = _schema(a=_col("int"), new=_col("str"))
    report = detect_drift(base, cur)
    kinds = {f["kind"]: f for f in report["findings"]}
    assert kinds["added_column"]["severity"] == "warning"
    assert kinds["removed_column"]["severity"] == "error"
    assert report["summary"]["breaking"] is True


def test_type_changes():
    base = _schema(n=_col("int"), m=_col("int"))
    cur = _schema(n=_col("float"), m=_col("str"))
    report = detect_drift(base, cur)
    tcs = sorted(
        (f for f in report["findings"] if f["kind"] == "type_change"),
        key=lambda f: f["column"],
    )
    assert tcs[0]["severity"] == "error"  # int -> str is lossy
    assert tcs[1]["severity"] == "warning"  # int -> float widens


def test_nullability_change():
    base = _schema(a=_col("int", nullable=False))
    cur = _schema(a=_col("int", nullable=True))
    report = detect_drift(base, cur)
    assert report["findings"][0]["kind"] == "nullability_change"
    assert report["findings"][0]["severity"] == "warning"


def test_possible_rename():
    base = _schema(customer_id=_col("int"))
    cur = _schema(customer_identifier=_col("int"))
    report = detect_drift(base, cur)
    kinds = [f["kind"] for f in report["findings"]]
    assert kinds == ["possible_rename"]
    rename = report["findings"][0]
    assert rename["severity"] == "info"
    assert rename["from"] == "customer_id"
    assert rename["to"] == "customer_identifier"


def test_rename_requires_same_type():
    base = _schema(customer_id=_col("int"))
    cur = _schema(customer_identifier=_col("str"))
    report = detect_drift(base, cur)
    kinds = sorted(f["kind"] for f in report["findings"])
    assert kinds == ["added_column", "removed_column"]  # no rename suggested


def test_end_to_end_examples():
    from drift.infer import snapshot_csv

    base = snapshot_csv("examples/orders_v1.csv")
    cur = snapshot_csv("examples/orders_v2.csv")
    report = detect_drift(base, cur)
    kinds = sorted(f["kind"] for f in report["findings"])
    assert kinds == [
        "added_column",
        "added_column",
        "nullability_change",  # amount_usd has a null in v2
        "removed_column",
        "type_change",
    ]
    assert report["summary"]["breaking"] is True
