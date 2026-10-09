# schema-drift-detector

Detect **schema drift between CSV loads** and quarantine the fallout.
Snapshot a load's schema (columns, inferred types, nullability) to a JSON
baseline, diff every new load against it, and split the incoming file into
a clean file (baseline columns only, type-valid rows) plus a quarantine
file (offending rows with reasons, including unexpected-column values —
nothing is silently dropped). Zero runtime dependencies: the inferencer is
a small hand-rolled type checker, not pandas. Portfolio project.

## Layout

```
drift/
  infer.py       # type inference + CSV schema snapshotting (bool/int/float/date/datetime/str)
  detect.py      # baseline-vs-current diff: added/removed/renamed columns, type + nullability changes
  quarantine.py  # split a load into clean.csv and quarantine.csv
  cli.py         # CLI: snapshot | detect | quarantine
examples/
  orders_v1.csv  # baseline load (5 columns)
  orders_v2.csv  # drifted load: 2 columns added, 1 removed, float->str, new nulls, a bad row
tests/           # pytest: inference, detection, quarantine
```

## Quickstart

```bash
pip install -r requirements.txt   # pytest only; the tool itself is stdlib-only

# 1. snapshot the good load
python -m drift.cli snapshot --csv examples/orders_v1.csv --out baseline.json

# 2. diff the next load against it (exit 1 if breaking drift found)
python -m drift.cli detect --baseline baseline.json \
  --csv examples/orders_v2.csv --out report.json
```

Example output:

```
drift: examples/orders_v2.csv vs baseline.json -> report.json
  findings=5 errors=2 warnings=3
  [warning] added_column: currency column not present in baseline
  [warning] added_column: notes column not present in baseline
  [error] removed_column: is_refund column present in baseline is gone
  [error] type_change: amount_usd type changed float -> str
  [warning] nullability_change: amount_usd column was non-nullable in baseline, nulls now present
```

```bash
# 3. quarantine: clean file keeps only baseline columns; bad rows go aside with reasons
python -m drift.cli quarantine --baseline baseline.json \
  --csv examples/orders_v2.csv --clean clean.csv --quarantine quarantine.csv
```

```
quarantine: examples/orders_v2.csv
  clean=4 quarantined=1
  dropped columns: currency, notes
```

`quarantine.csv` keeps the offending data, so you can fix and re-load it:

```csv
row,reason,unexpected_currency,unexpected_notes
3,amount_usd: 'one-fifty' is not a valid float,USD,manual entry
```

## Design notes

- **Narrowest-type inference.** `1,2,3` → int, `1.5` → float, ISO dates →
  date; anything mixed or unrecognized → str. An all-null column infers as
  str (unknown is honest).
- **Widening is a warning, narrowing is an error.** int→float and
  date→datetime are safe (warning); float→str or int→str loses information
  (error). Removed columns are errors; added columns are warnings —
  downstream queries break on the former, not the latter.
- **Possible renames are suggestions, not decisions.** A removed + added
  pair with the same inferred type and a name similarity ≥ 0.7 is reported
  as `possible_rename` (info severity) — the tool never silently rewrites a
  column mapping.
- **Exit code 1 on breaking drift** so the `detect` step can gate a
  pipeline: warnings pass, errors stop the load.
- **Quarantine preserves evidence.** Type-violating rows keep their full
  raw data plus the unexpected-column values in the quarantine file, so the
  load is auditable and recoverable.

## Honesty notes

This is a portfolio demo of schema-diffing and quarantine logic on CSVs,
not production lineage or warehouse DDL management — it doesn't claim
integration with dbt, Airflow, or any cloud warehouse.
