"""Remint gold tokens with Dadma boundaries + required char_spans + kind remap.

Does not invent sentences. Leaves ezafe null (blind labeling).
Requires Dadma cache (env-gated).
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
    DOMAIN_SOURCE_KIND,
    GoldExample,
    align_token_char_spans,
    canonical_domain,
    installed_dadmatools_version,
    load_ezafe_gold,
    mint_dadma_tokens,
    resolve_source_kind,
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
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if not os.environ.get("PERSIAN_SEO_DADMA_CACHE"):
        repo_cache = ROOT / "cache" / "dadmatools"
        if repo_cache.is_dir():
            os.environ["PERSIAN_SEO_DADMA_CACHE"] = str(repo_cache.resolve())
        else:
            print("ERROR: PERSIAN_SEO_DADMA_CACHE required", file=sys.stderr)
            return 2

    from persian_seo_normalizer import detect_ezafe

    examples = load_ezafe_gold(args.gold, require_labeled=False)
    minted_at = utc_now_iso()
    version = installed_dadmatools_version()
    out_rows: list[GoldExample] = []
    for ex in examples:
        model_tokens = tuple(m.token for m in detect_ezafe(ex.text))
        tokens, spans, src, ver, ts = mint_dadma_tokens(
            ex.text,
            token_strings=model_tokens,
            minted_at=minted_at,
            version=version,
        )
        domain = canonical_domain(ex.source_url) or ex.source
        if domain == "fa.wikipedia.org" or "wikipedia" in domain:
            source = "fa.wikipedia.org"
        else:
            source = domain
        kind = resolve_source_kind(
            source=source,
            source_kind=DOMAIN_SOURCE_KIND.get(source, ex.source_kind),
            source_url=ex.source_url,
        )
        out_rows.append(
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
                source=source,
                source_kind=kind,
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
    out = args.out or args.gold
    write_ezafe_gold(out, out_rows)
    # sanity: round-trip span check
    bad = 0
    for ex in out_rows:
        try:
            align_token_char_spans(ex.text, ex.tokens)
        except ValueError:
            bad += 1
    print(
        json.dumps(
            {
                "wrote": len(out_rows),
                "out": str(out),
                "dadmatools_version": version,
                "align_failures": bad,
            },
            ensure_ascii=False,
        )
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
