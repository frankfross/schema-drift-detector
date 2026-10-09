"""Quarantine unexpected columns and type-violating rows.

Given a baseline schema and a new CSV, split the load into:
  - clean.csv      : only baseline columns (in baseline order), rows whose
                     values parse as the baseline type
  - quarantine.csv : original row index, reason, and the offending data,
                     including any unexpected-column values (nothing is
                     silently dropped)
"""

from __future__ import annotations

import csv

from .infer import parse_value


def quarantine(
    baseline: dict,
    csv_path: str,
    clean_path: str,
    quarantine_path: str,
) -> dict:
    base_cols = baseline["columns"]
    base_names = list(base_cols)

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path}: no header row found")
        incoming = list(reader.fieldnames)
        unexpected = [c for c in incoming if c not in base_cols]

        kept_rows: list[dict] = []
        quarantined: list[dict] = []
        for idx, row in enumerate(reader, start=2):  # header is line 1
            reasons: list[str] = []
            for c in base_names:
                v = row.get(c) or ""
                if v.strip() != "" and not parse_value(v, base_cols[c]["type"]):
                    reasons.append(
                        f"{c}: {v!r} is not a valid {base_cols[c]['type']}"
                    )
            if reasons:
                quarantined.append({"row": idx, "reason": "; ".join(reasons),
                                    "raw": dict(row)})
            else:
                kept_rows.append({c: row.get(c, "") for c in base_names})

    with open(clean_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=base_names)
        writer.writeheader()
        writer.writerows(kept_rows)

    q_fields = ["row", "reason", *[f"unexpected_{c}" for c in unexpected]]
    with open(quarantine_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=q_fields)
        writer.writeheader()
        for q in quarantined:
            writer.writerow(
                {"row": q["row"], "reason": q["reason"],
                 **{f"unexpected_{c}": q["raw"].get(c, "") for c in unexpected}}
            )

    stats = {
        "rows_read": len(kept_rows) + len(quarantined),
        "rows_clean": len(kept_rows),
        "rows_quarantined": len(quarantined),
        "unexpected_columns_dropped": unexpected,
        "baseline_columns": base_names,
    }
    return stats
