"""Build a blind-labeling CSV worksheet from ezafe gold JSONL.

Never pre-fills ezafe labels from any model.
Output: UTF-8 with BOM for Excel on Windows.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    load_ezafe_gold,
    write_worksheet_csv,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_worksheet.csv",
    )
    args = parser.parse_args(argv)
    examples = load_ezafe_gold(args.gold, require_labeled=False)
    n = write_worksheet_csv(args.out, examples)
    print(f"Wrote {n} token rows for {len(examples)} sentences -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
