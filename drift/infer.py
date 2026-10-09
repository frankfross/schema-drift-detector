"""Schema inference for CSV files.

Reads a CSV, samples values per column, and infers a type for each one.
Deliberately stdlib-only: no pandas, no pyarrow.
"""

from __future__ import annotations

import csv
import datetime
import re

#: types are ordered from narrowest to widest
TYPES = ("bool", "int", "float", "date", "datetime", "str")

_BOOL_TRUE = {"true", "t", "yes", "y"}
_BOOL_FALSE = {"false", "f", "no", "n"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def parse_value(value: str, type_name: str) -> bool:
    """True if *value* is representable as *type_name*."""
    v = value.strip()
    if v == "":
        return True  # nulls parse as anything
    if type_name == "bool":
        return v.lower() in _BOOL_TRUE | _BOOL_FALSE | {"1", "0"}
    if type_name == "int":
        try:
            int(v)
            return True
        except ValueError:
            return False
    if type_name == "float":
        try:
            float(v)
            return True
        except ValueError:
            return False
    if type_name == "date":
        return bool(_DATE_RE.match(v)) and _valid_date(v)
    if type_name == "datetime":
        if not _DATETIME_RE.match(v):
            return False
        try:
            datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
    return True  # str accepts everything


def _valid_date(v: str) -> bool:
    try:
        datetime.date.fromisoformat(v)
        return True
    except ValueError:
        return False


def infer_type(values: list[str]) -> str:
    """Infer the narrowest type that fits every non-null sample value."""
    non_null = [v for v in values if v.strip() != ""]
    if not non_null:
        return "str"  # all-null column: unknown, treat as str
    for type_name in TYPES:
        if all(parse_value(v, type_name) for v in non_null):
            return type_name
    return "str"


def snapshot_csv(path: str, sample_rows: int = 10_000) -> dict:
    """Snapshot the schema of a CSV file into a JSON-serializable dict."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: no header row found")
        columns = list(reader.fieldnames)
        samples: dict[str, list[str]] = {c: [] for c in columns}
        nulls: dict[str, int] = {c: 0 for c in columns}
        row_count = 0
        for row in reader:
            row_count += 1
            for c in columns:
                v = row.get(c) or ""
                if v.strip() == "":
                    nulls[c] += 1
                elif len(samples[c]) < sample_rows:
                    samples[c].append(v)
    schema = {
        "row_count": row_count,
        "columns": {
            c: {
                "type": infer_type(samples[c]),
                "nullable": nulls[c] > 0,
                "null_fraction": round(nulls[c] / row_count, 4) if row_count else 0.0,
            }
            for c in columns
        },
    }
    return schema
