"""Tests for quarantine splitting."""

import csv

from drift.infer import snapshot_csv
from drift.quarantine import quarantine


def test_quarantine_splits_bad_rows(tmp_path):
    base = snapshot_csv("examples/orders_v1.csv")
    clean = tmp_path / "clean.csv"
    quar = tmp_path / "quarantine.csv"
    stats = quarantine(base, "examples/orders_v2.csv", str(clean), str(quar))

    assert stats["rows_read"] == 5
    assert stats["rows_clean"] == 4
    assert stats["rows_quarantined"] == 1  # "one-fifty" is not a float
    assert sorted(stats["unexpected_columns_dropped"]) == ["currency", "notes"]

    with open(clean, newline="") as fh:
        reader = csv.DictReader(fh)
        assert list(reader.fieldnames) == list(base["columns"])
        rows = list(reader)
        assert len(rows) == 4
        assert all("currency" not in r for r in rows)

    with open(quar, newline="") as fh:
        reader = csv.DictReader(fh)
        qrows = list(reader)
        assert len(qrows) == 1
        assert qrows[0]["row"] == "3"  # header is line 1, bad row is line 3
        assert "amount_usd" in qrows[0]["reason"]


def test_quarantine_clean_load(tmp_path):
    base = snapshot_csv("examples/orders_v1.csv")
    clean = tmp_path / "clean.csv"
    quar = tmp_path / "quarantine.csv"
    stats = quarantine(base, "examples/orders_v1.csv", str(clean), str(quar))
    assert stats["rows_quarantined"] == 0
    assert stats["rows_clean"] == 5
    assert stats["unexpected_columns_dropped"] == []
