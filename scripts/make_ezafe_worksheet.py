"""Build a blind-labeling CSV worksheet from ezafe gold JSONL.

Never pre-fills ezafe labels from any model.
Default: stratified batch (25 wiki + 25 commercial) with fixed seed.
Output: UTF-8 with BOM for Excel on Windows.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    is_commercial_example,
    is_wikipedia_example,
    load_ezafe_gold,
    sample_stratified_labeling_batch,
    write_worksheet_csv,
)

DEFAULT_SEED = 20260728


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--n-wiki", type=int, default=25)
    parser.add_argument("--n-commercial", type=int, default=25)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Write every gold row (not stratified batch).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="CSV path (default includes seed in filename).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest JSON path (default next to --out).",
    )
    args = parser.parse_args(argv)

    examples = load_ezafe_gold(args.gold, require_labeled=False)
    if args.all:
        batch = examples
        out = args.out or (ROOT / "data" / "gold" / "ezafe_worksheet_all.csv")
    else:
        batch = sample_stratified_labeling_batch(
            examples,
            n_wiki=args.n_wiki,
            n_commercial=args.n_commercial,
            seed=args.seed,
        )
        out = args.out or (
            ROOT / "data" / "gold" / f"ezafe_worksheet_batch1_seed{args.seed}.csv"
        )

    n = write_worksheet_csv(out, batch)
    manifest = {
        "seed": args.seed,
        "n_wiki": sum(1 for ex in batch if is_wikipedia_example(ex)),
        "n_commercial": sum(1 for ex in batch if is_commercial_example(ex)),
        "ids": [ex.id for ex in batch],
        "source_kinds": {
            k: sum(1 for ex in batch if ex.source_kind == k)
            for k in sorted({ex.source_kind for ex in batch})
        },
        "worksheet": str(out),
    }
    man_path = args.manifest or out.with_suffix(".manifest.json")
    man_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "token_rows_incl_sentence_headers": n,
                "sentences": len(batch),
                "worksheet": str(out),
                "manifest": str(man_path),
                **{k: manifest[k] for k in ("seed", "n_wiki", "n_commercial", "source_kinds")},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
