"""Evaluate detect_ezafe against data/gold/ezafe_gold.jsonl.

Usage:
  python scripts/eval_ezafe_gold.py
  python scripts/eval_ezafe_gold.py --gold path/to/file.jsonl

Requires PERSIAN_SEO_DADMA_CACHE for the real backend. Does not invent metrics
when the gold file is missing or empty.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    confusion_counts,
    format_metrics_report,
    load_ezafe_gold,
)


def _pred_ezafe_flags(text: str, tokens: tuple[str, ...]) -> list[int]:
    from persian_seo_normalizer import detect_ezafe

    marks = detect_ezafe(text)
    if len(marks) != len(tokens):
        raise RuntimeError(
            f"token alignment failed for text={text!r}: "
            f"gold_tokens={list(tokens)!r} model_tokens={[m.token for m in marks]!r}"
        )
    for gold_tok, mark in zip(tokens, marks, strict=True):
        if gold_tok != mark.token:
            raise RuntimeError(
                f"token text mismatch: gold={gold_tok!r} model={mark.token!r} in {text!r}"
            )
    return [1 if m.has_ezafe else 0 for m in marks]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
        help="Path to JSONL gold file",
    )
    args = parser.parse_args(argv)

    try:
        examples = load_ezafe_gold(args.gold)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    unverified = sum(1 for ex in examples if not ex.verified)
    if unverified:
        print(
            f"WARNING: {unverified}/{len(examples)} examples have verified=false "
            "(placeholder samples; do not treat F1 as product claim).",
            file=sys.stderr,
        )

    if not os.environ.get("PERSIAN_SEO_DADMA_CACHE"):
        print(
            "ERROR: set PERSIAN_SEO_DADMA_CACHE to an absolute prepared cache path.",
            file=sys.stderr,
        )
        return 2

    gold_all: list[int] = []
    pred_all: list[int] = []
    for ex in examples:
        pred = _pred_ezafe_flags(ex.text, ex.tokens)
        gold_all.extend(ex.ezafe)
        pred_all.extend(pred)

    counts = confusion_counts(gold_all, pred_all)
    print(format_metrics_report(counts, n_examples=len(examples), n_tokens=len(gold_all)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
