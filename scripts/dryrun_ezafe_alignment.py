"""Dry-run token alignment: gold worksheet tokens vs detect_ezafe tokens.

No quality metrics. No ezafe labels are read or written from the model.
Optional --apply-dadma-tokens remints token boundaries only (ezafe stays null).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    ALIGNMENT_FAIL_THRESHOLD,
    GoldExample,
    classify_alignment_mismatch,
    installed_dadmatools_version,
    load_ezafe_gold,
    mint_dadma_tokens,
    tokens_aligned,
    utc_now_iso,
    write_ezafe_gold,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
    )
    parser.add_argument(
        "--apply-dadma-tokens",
        action="store_true",
        help="Rewrite tokens from Dadma boundaries; leave ezafe null (blind).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSONL when applying Dadma tokens (default: overwrite --gold).",
    )
    args = parser.parse_args(argv)

    if not os.environ.get("PERSIAN_SEO_DADMA_CACHE"):
        repo_cache = ROOT / "cache" / "dadmatools"
        if repo_cache.is_dir():
            os.environ["PERSIAN_SEO_DADMA_CACHE"] = str(repo_cache.resolve())
        else:
            print(
                "ERROR: set PERSIAN_SEO_DADMA_CACHE to an absolute prepared cache path.",
                file=sys.stderr,
            )
            return 2

    from persian_seo_normalizer import detect_ezafe

    examples = load_ezafe_gold(args.gold, require_labeled=False)
    n_aligned = 0
    n_unaligned = 0
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    by_strata: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    unaligned_samples: list[dict] = []
    reminted: list[GoldExample] = []

    for ex in examples:
        model_tokens = tuple(m.token for m in detect_ezafe(ex.text))
        ours = list(ex.tokens)
        model_list = list(model_tokens)
        aligned = tokens_aligned(ours, model_list)
        key = "aligned" if aligned else "unaligned"
        if aligned:
            n_aligned += 1
        else:
            n_unaligned += 1
            reason = classify_alignment_mismatch(ours, model_list)
            reason_counts[reason] += 1
            if len(unaligned_samples) < 10:
                unaligned_samples.append(
                    {
                        "id": ex.id,
                        "source": ex.source,
                        "strata": list(ex.strata),
                        "reason": reason,
                        "text": ex.text,
                        "ours": ours,
                        "model": model_list,
                    }
                )
        by_source[ex.source or "?"][key] += 1
        if not ex.strata:
            by_strata["(none)"][key] += 1
        else:
            for s in ex.strata:
                by_strata[s][key] += 1

        if args.apply_dadma_tokens:
            tokens, spans, src, ver, ts = mint_dadma_tokens(
                ex.text,
                token_strings=model_tokens,
                minted_at=utc_now_iso(),
                version=installed_dadmatools_version(),
            )
            reminted.append(
                GoldExample(
                    id=ex.id,
                    text=ex.text,
                    tokens=tokens,
                    char_spans=spans,
                    ezafe=None,
                    note=ex.note,
                    verified=False,
                    ambiguous=ex.ambiguous,
                    strata=ex.strata,
                    source=ex.source,
                    source_kind=ex.source_kind,
                    source_url=ex.source_url,
                    license=ex.license,
                    collected_at=ex.collected_at,
                    page_title=ex.page_title,
                    revision_id=ex.revision_id,
                    labeled_by="",
                    labeled_at="",
                    tokenizer_source=src,
                    dadmatools_version=ver,
                    tokens_minted_at=ts,
                    extra=dict(ex.extra),
                )
            )

    total = n_aligned + n_unaligned
    fail_rate = (n_unaligned / total) if total else 0.0

    def rate_block(counter: Counter[str]) -> dict:
        a = counter.get("aligned", 0)
        u = counter.get("unaligned", 0)
        t = a + u
        return {
            "n_aligned": a,
            "n_unaligned": u,
            "unaligned_rate": (u / t) if t else 0.0,
        }

    report = {
        "total": total,
        "n_aligned": n_aligned,
        "n_unaligned": n_unaligned,
        "unaligned_rate": fail_rate,
        "threshold": ALIGNMENT_FAIL_THRESHOLD,
        "decision": (
            "switch_token_contract_to_dadma"
            if fail_rate > ALIGNMENT_FAIL_THRESHOLD
            else "keep_hand_tokens"
        ),
        "by_source": {k: rate_block(v) for k, v in sorted(by_source.items())},
        "by_strata": {k: rate_block(v) for k, v in sorted(by_strata.items())},
        "mismatch_reasons": dict(reason_counts),
        "unaligned_samples": unaligned_samples,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.apply_dadma_tokens:
        out = args.out or args.gold
        write_ezafe_gold(out, reminted)
        print(f"Wrote Dadma-tokenized unlabeled gold -> {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
