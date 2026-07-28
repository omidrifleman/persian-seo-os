"""Expand ecommerce gold sentences from allowed Persian shop/mag domains.

One-time network harvest. Does not invent text. Reports shortfall if <40.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    MIN_ECOMMERCE_TARGET,
    SOURCE_KIND_ECOMMERCE,
    GoldExample,
    align_token_char_spans,
    canonical_domain,
    detect_strata,
    load_ezafe_gold,
    tokenize_raw,
    utc_now_iso,
    whitespace_word_count,
    write_ezafe_gold,
)

UA = "persian-seo-os-ezafe-gold/0.1 (research sampling; contact: local-dev)"

# Only domains already checked: robots allow + no ai-train=no Content-Signal.
ECOMMERCE_URLS = [
    "https://www.digikala.com/mag/",
    "https://www.digikala.com/mag/category/buying-guide/",
    "https://www.digikala.com/mag/best-ceramic-cookware-set/",
    "https://www.digikala.com/mag/best-shampoo-for-hair-transplant/",
    "https://www.digikala.com/mag/buy-quarter-coin-or-full-coin/",
    "https://www.digikala.com/mag/baby-girl-gifts-ideas/",
    "https://www.digikala.com/mag/best-birthday-gift-ideas-for-spouse/",
    "https://blog.okala.com/",
    "https://www.basalam.com/",
    "https://emalls.ir/",
    "https://www.modiseh.com/",
    "https://www.modiseh.com/women",
    "https://www.modiseh.com/men",
    "https://www.okala.com/",
]


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _candidate_ok(sentence: str) -> bool:
    n = whitespace_word_count(sentence)
    if not (5 <= n <= 15):
        return False
    letters = re.findall(r"[\u0600-\u06FF]", sentence)
    return len(letters) >= 8


def harvest(limit: int = 80) -> list[tuple[str, str, str]]:
    """Return list of (sentence, url, domain)."""
    collected_at = utc_now_iso()
    del collected_at
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for url in ECOMMERCE_URLS:
        if len(out) >= limit:
            break
        try:
            page = _get(url)
        except (urllib.error.URLError, TimeoutError, UnicodeError) as exc:
            print(f"WARN skip {url}: {exc}", file=sys.stderr)
            continue
        text = _strip_html(page)
        domain = canonical_domain(url)
        for sent in re.split(r"(?<=[.!?؟۔\n])\s+", text):
            sent = re.sub(r"\s+", " ", sent).strip()
            if len(sent) > 220 or not _candidate_ok(sent) or sent in seen:
                continue
            if re.search(
                r"ورود|ثبت[\s‌]?نام|سبد خرید|اپلیکیشن|دانلود|کپی‌رایت|Copyright",
                sent,
                re.IGNORECASE,
            ):
                continue
            shop_host = domain in {
                "digikala.com",
                "blog.okala.com",
                "okala.com",
                "basalam.com",
                "emalls.ir",
                "torob.com",
                "modiseh.com",
            }
            # On verified shop hosts keep all length-ok Persian sentences
            # (category chrome still filtered above). Elsewhere require shop cues.
            if not shop_host and not re.search(
                r"خرید|محصول|قیمت|دسته‌?بند|کالا|ارسال|گارانتی|تومان|سبد|فروشگاه|برند",
                sent,
            ):
                continue
            toks = tokenize_raw(sent)
            if not (5 <= len(toks) <= 15):
                continue
            seen.add(sent)
            out.append((sent, url, domain))
            if len(out) >= limit:
                break
        time.sleep(0.4)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--target", type=int, default=MIN_ECOMMERCE_TARGET)
    args = parser.parse_args(argv)

    existing = load_ezafe_gold(args.gold, require_labeled=False)
    ecom = [ex for ex in existing if ex.source_kind == SOURCE_KIND_ECOMMERCE]
    have = len(ecom)
    need = max(0, args.target - have)
    print(f"ecommerce_have={have} need={need}", flush=True)

    harvested = harvest(limit=max(need * 3, 40))
    existing_texts = {ex.text for ex in existing}
    existing_ids = {ex.id for ex in existing}
    collected_at = utc_now_iso()
    added: list[GoldExample] = []
    # Placeholder whitespace tokens; remint_gold_char_spans fills Dadma+spans.
    for sent, url, domain in harvested:
        if len(ecom) + len(added) >= args.target:
            break
        if sent in existing_texts:
            continue
        tokens = tuple(tokenize_raw(sent))
        try:
            spans = align_token_char_spans(sent, tokens)
        except ValueError:
            continue
        eid = f"ecom-{domain.split('.')[0]}-{len(added):04d}"
        if eid in existing_ids:
            eid = f"ecom-{len(existing)+len(added):04d}"
        added.append(
            GoldExample(
                id=eid,
                text=sent,
                tokens=tokens,
                char_spans=spans,
                ezafe=None,
                verified=False,
                strata=tuple(detect_strata(sent)),
                source=domain,
                source_kind=SOURCE_KIND_ECOMMERCE,
                source_url=url,
                license="source-site-terms (snippet for evaluation only)",
                collected_at=collected_at,
                note="unlabeled ecommerce candidate; remint Dadma spans next",
                tokenizer_source="whitespace_raw",
                dadmatools_version="",
                tokens_minted_at="",
            )
        )

    merged = list(existing) + added
    out = args.out or args.gold
    write_ezafe_gold(out, merged)
    final_ecom = sum(1 for ex in merged if ex.source_kind == SOURCE_KIND_ECOMMERCE)
    domains = sorted({ex.source for ex in merged if ex.source_kind == SOURCE_KIND_ECOMMERCE})
    report = {
        "added": len(added),
        "ecommerce_final": final_ecom,
        "ecommerce_target": args.target,
        "shortfall": max(0, args.target - final_ecom),
        "ecommerce_domains": domains,
        "out": str(out),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
