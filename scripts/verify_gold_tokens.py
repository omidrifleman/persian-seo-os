"""Verify gold tokens/char_spans still match the installed DadmaTools tokenizer.

Env-gated: requires PERSIAN_SEO_DADMA_CACHE (or repo cache/dadmatools).
No network. Exit 1 if any record mismatches; exit 2 if cache missing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    installed_dadmatools_version,
    load_ezafe_gold,
    verify_example_tokens_against_model,
)


def _ensure_cache_env() -> int | None:
    if os.environ.get("PERSIAN_SEO_DADMA_CACHE"):
        return None
    repo_cache = ROOT / "cache" / "dadmatools"
    if repo_cache.is_dir():
        os.environ["PERSIAN_SEO_DADMA_CACHE"] = str(repo_cache.resolve())
        return None
    print(
        "ERROR: set PERSIAN_SEO_DADMA_CACHE to an absolute prepared cache path.",
        file=sys.stderr,
    )
    return 2


def verify_gold_file(gold_path: Path) -> dict:
    from persian_seo_normalizer import detect_ezafe

    examples = load_ezafe_gold(gold_path, require_labeled=False)
    mismatches: list[dict] = []
    for ex in examples:
        model_tokens = [m.token for m in detect_ezafe(ex.text)]
        problems = verify_example_tokens_against_model(ex, model_tokens=model_tokens)
        if problems:
            mismatches.append(
                {
                    "id": ex.id,
                    "problems": problems,
                    "stored_tokens": list(ex.tokens),
                    "model_tokens": model_tokens,
                    "stored_spans": [list(s) for s in ex.char_spans],
                    "tokenizer_source": ex.tokenizer_source,
                    "dadmatools_version": ex.dadmatools_version,
                }
            )
    return {
        "n_checked": len(examples),
        "n_mismatch": len(mismatches),
        "installed_dadmatools_version": installed_dadmatools_version(),
        "mismatches": mismatches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
    )
    args = parser.parse_args(argv)
    gate = _ensure_cache_env()
    if gate is not None:
        return gate
    report = verify_gold_file(args.gold)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["n_mismatch"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
