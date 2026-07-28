"""Evaluate detect_ezafe against labeled ezafe gold (split reports).

Outputs three levels: overall, by source rollup (wikipedia vs commercial),
by strata. Slices with fewer than MIN_EVAL_EXAMPLES examples print
insufficient_sample and omit F1 numbers.

Refuses to score if gold tokens/char_spans do not match the installed
DadmaTools tokenizer (shifted labels would silently corrupt metrics).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    evaluate_metric_splits,
    load_ezafe_gold,
)
from verify_gold_tokens import _ensure_cache_env, verify_gold_file


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

    gate = _ensure_cache_env()
    if gate is not None:
        return gate

    verify_report = verify_gold_file(args.gold)
    if verify_report["n_mismatch"]:
        print(
            "ERROR: gold tokens/char_spans do not match installed DadmaTools. "
            "Refusing to score (labels would be shifted).",
            file=sys.stderr,
        )
        print(json.dumps(verify_report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    try:
        examples = load_ezafe_gold(args.gold, require_labeled=True)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    predictions = {
        ex.id: _pred_ezafe_flags(ex.text, ex.tokens) for ex in examples
    }
    report = evaluate_metric_splits(examples, predictions=predictions)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
