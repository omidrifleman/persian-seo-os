"""Normalize gold source fields to real domains + drop unclear robots domains.

One-time offline rewrite of data/gold/ezafe_gold.jsonl (no network required if
--robots-report is supplied). Tests must not call live robots.txt.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    SOURCE_KIND_WIKIPEDIA,
    GoldExample,
    canonical_domain,
    is_wikipedia_example,
    load_ezafe_gold,
    with_source_fields,
    write_ezafe_gold,
)

# Legacy bucket names stored before domain migration.
_LEGACY_BUCKETS = {"blog_portal", "shop_mag", "news_portal", "shop_wiki_stub", "web"}

# Domains whose robots/Content-Signal status is not clearly allow for this use.
# technolife.ir: Content-Signal ai-train=no (ambiguous for ML eval gold).
BLOCKED_OR_UNCLEAR_DOMAINS = frozenset({"technolife.ir"})


def resolve_source_kind(ex: GoldExample) -> str:
    if is_wikipedia_example(ex) or ex.source_kind == SOURCE_KIND_WIKIPEDIA:
        return SOURCE_KIND_WIKIPEDIA
    if ex.source_kind in _LEGACY_BUCKETS:
        return ex.source_kind
    if ex.source in _LEGACY_BUCKETS:
        return ex.source
    return ex.source_kind or "web"


def migrate_example(ex: GoldExample) -> GoldExample | None:
    kind = resolve_source_kind(ex)
    if kind == SOURCE_KIND_WIKIPEDIA:
        return with_source_fields(
            ex, source="fa.wikipedia.org", source_kind=SOURCE_KIND_WIKIPEDIA
        )
    domain = canonical_domain(ex.source_url)
    if not domain:
        return None
    if domain in BLOCKED_OR_UNCLEAR_DOMAINS:
        return None
    # If source was already a domain, prefer URL domain as source of truth.
    return with_source_fields(ex, source=domain, source_kind=kind)


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
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print domain counts only; do not write.",
    )
    args = parser.parse_args(argv)

    examples = load_ezafe_gold(args.gold, require_labeled=False)
    kept: list[GoldExample] = []
    dropped: Counter[str] = Counter()
    before_web = Counter()
    for ex in examples:
        if is_wikipedia_example(ex):
            continue
        before_web[canonical_domain(ex.source_url) or ex.source] += 1

    for ex in examples:
        migrated = migrate_example(ex)
        if migrated is None:
            dropped[canonical_domain(ex.source_url) or ex.source or "?"] += 1
            continue
        kept.append(migrated)

    after_web = Counter(
        ex.source for ex in kept if not is_wikipedia_example(ex)
    )
    report = {
        "before_nonwiki_domains": dict(before_web),
        "after_nonwiki_domains": dict(after_web),
        "dropped_domains": dict(dropped),
        "n_before": len(examples),
        "n_after": len(kept),
        "n_wiki": sum(1 for ex in kept if is_wikipedia_example(ex)),
        "n_web": sum(1 for ex in kept if not is_wikipedia_example(ex)),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    out = args.out or args.gold
    write_ezafe_gold(out, kept)
    print(f"Wrote {len(kept)} rows -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
