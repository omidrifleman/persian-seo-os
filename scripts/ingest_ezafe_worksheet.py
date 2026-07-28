"""Ingest a human-labeled ezafe worksheet CSV back into gold JSONL.

Strict validation: ezafe must be 0/1; length must match tokens; mismatches error
with line/id context — never auto-corrected. Does not call any ML model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    ingest_worksheet_csv,
    load_ezafe_gold,
    write_ezafe_gold,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
        help="Base unlabeled/partial gold JSONL",
    )
    parser.add_argument(
        "--worksheet",
        type=Path,
        required=True,
        help="Human-filled CSV (utf-8-sig)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSONL (default: overwrite --gold)",
    )
    parser.add_argument("--labeled-by", required=True, help="Annotator id/name")
    args = parser.parse_args(argv)

    base_list = load_ezafe_gold(args.gold, require_labeled=False)
    base_map = {ex.id: ex for ex in base_list}
    try:
        labeled = ingest_worksheet_csv(
            args.worksheet, base_examples=base_map, labeled_by=args.labeled_by
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Keep unlabeled rows that were not in the worksheet; replace labeled ids.
    labeled_ids = {ex.id for ex in labeled}
    merged = [ex for ex in base_list if ex.id not in labeled_ids] + labeled
    # Stable order: original order with updates.
    by_id = {ex.id: ex for ex in merged}
    ordered = [by_id[ex.id] for ex in base_list if ex.id in by_id]
    for ex in labeled:
        if ex.id not in {x.id for x in ordered}:
            ordered.append(ex)

    out = args.out or args.gold
    write_ezafe_gold(out, ordered)
    print(
        json.dumps(
            {
                "labeled": len(labeled),
                "total": len(ordered),
                "out": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
