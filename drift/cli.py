"""CLI: snapshot, detect, quarantine."""

from __future__ import annotations

import argparse
import json
import sys

from .detect import detect_drift
from .infer import snapshot_csv
from .quarantine import quarantine


def cmd_snapshot(args: argparse.Namespace) -> int:
    schema = snapshot_csv(args.csv)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2)
    print(f"snapshot: {args.csv} -> {args.out} "
          f"({len(schema['columns'])} columns, {schema['row_count']} rows)")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    with open(args.baseline, encoding="utf-8") as fh:
        baseline = json.load(fh)
    current = snapshot_csv(args.csv)
    report = detect_drift(baseline, current)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    s = report["summary"]
    print(f"drift: {args.csv} vs {args.baseline} -> {args.out}")
    print(f"  findings={len(report['findings'])} "
          f"errors={s['errors']} warnings={s['warnings']}")
    for f in report["findings"]:
        print(f"  [{f['severity']}] {f['kind']}: {f.get('column', '')} "
              f"{f.get('detail', '')}".rstrip())
    return 1 if s["breaking"] else 0


def cmd_quarantine(args: argparse.Namespace) -> int:
    with open(args.baseline, encoding="utf-8") as fh:
        baseline = json.load(fh)
    stats = quarantine(baseline, args.csv, args.clean, args.quarantine)
    print(f"quarantine: {args.csv}")
    print(f"  clean={stats['rows_clean']} quarantined={stats['rows_quarantined']}")
    if stats["unexpected_columns_dropped"]:
        print(f"  dropped columns: {', '.join(stats['unexpected_columns_dropped'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="drift", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("snapshot", help="snapshot a CSV's schema to JSON")
    p.add_argument("--csv", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("detect", help="compare a CSV against a baseline snapshot")
    p.add_argument("--baseline", required=True)
    p.add_argument("--csv", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("quarantine",
                       help="split a CSV into clean + quarantined outputs")
    p.add_argument("--baseline", required=True)
    p.add_argument("--csv", required=True)
    p.add_argument("--clean", required=True)
    p.add_argument("--quarantine", required=True)
    p.set_defaults(func=cmd_quarantine)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
