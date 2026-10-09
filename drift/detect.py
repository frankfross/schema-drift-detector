"""Compare a baseline schema snapshot against a new load's schema.

Produces a drift report with severities:
  - error   : breaking change (removed column, lossy type change)
  - warning : needs attention (added column, widening type change, new nulls)
  - info    : harmless (possible rename suggestion)
"""

from __future__ import annotations

import difflib

#: widening = safe (warning); anything else between different types is lossy (error)
_WIDENING = {
    ("bool", "int"),
    ("int", "float"),
    ("date", "datetime"),
}
_LOSSLESS_SAME_FAMILY = {("int", "int"), ("float", "float"), ("str", "str")}


def _type_severity(old: str, new: str) -> str:
    if old == new:
        return "ok"
    if (old, new) in _WIDENING:
        return "warning"
    return "error"


def detect_drift(baseline: dict, current: dict, rename_threshold: float = 0.7) -> dict:
    base_cols = baseline["columns"]
    cur_cols = current["columns"]
    base_names = set(base_cols)
    cur_names = set(cur_cols)

    added = sorted(cur_names - base_names)
    removed = sorted(base_names - cur_names)

    type_changes = []
    nullability_changes = []
    for name in sorted(base_names & cur_names):
        old_t, new_t = base_cols[name]["type"], cur_cols[name]["type"]
        sev = _type_severity(old_t, new_t)
        if sev != "ok":
            type_changes.append(
                {"column": name, "from": old_t, "to": new_t, "severity": sev}
            )
        if not base_cols[name]["nullable"] and cur_cols[name]["nullable"]:
            nullability_changes.append(
                {
                    "column": name,
                    "severity": "warning",
                    "detail": "column was non-nullable in baseline, nulls now present",
                }
            )

    # Possible renames: a removed + added pair with similar names and same type.
    renames = []
    used_added: set[str] = set()
    for old in removed:
        best, best_score = None, 0.0
        for new in added:
            if new in used_added:
                continue
            if base_cols[old]["type"] != cur_cols[new]["type"]:
                continue
            score = difflib.SequenceMatcher(None, old, new).ratio()
            if score >= rename_threshold and score > best_score:
                best, best_score = new, score
        if best is not None:
            renames.append(
                {
                    "from": old,
                    "to": best,
                    "similarity": round(best_score, 3),
                    "severity": "info",
                }
            )
            used_added.add(best)

    renamed_old = {r["from"] for r in renames}
    renamed_new = {r["to"] for r in renames}

    findings = []
    for name in added:
        if name in renamed_new:
            continue
        findings.append(
            {
                "kind": "added_column",
                "column": name,
                "type": cur_cols[name]["type"],
                "severity": "warning",
                "detail": "column not present in baseline",
            }
        )
    for name in removed:
        if name in renamed_old:
            continue
        findings.append(
            {
                "kind": "removed_column",
                "column": name,
                "severity": "error",
                "detail": "column present in baseline is gone",
            }
        )
    for tc in type_changes:
        findings.append(
            {
                "kind": "type_change",
                "column": tc["column"],
                "from": tc["from"],
                "to": tc["to"],
                "severity": tc["severity"],
                "detail": f"type changed {tc['from']} -> {tc['to']}",
            }
        )
    for nc in nullability_changes:
        findings.append({"kind": "nullability_change", **nc})
    for r in renames:
        findings.append({"kind": "possible_rename", **r})

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "baseline_rows": baseline.get("row_count"),
        "current_rows": current.get("row_count"),
        "findings": findings,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "breaking": errors > 0,
        },
    }
