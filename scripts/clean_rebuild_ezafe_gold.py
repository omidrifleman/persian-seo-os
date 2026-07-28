"""Clean existing ezafe gold with body filters + wiki template dedupe.

Optionally tops up shortfalls via content-page / wiki harvest (with retries).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    MIN_ECOMMERCE_TARGET,
    SOURCE_KIND_ECOMMERCE,
    SOURCE_KIND_MAGAZINE,
    SOURCE_KIND_NEWS,
    SOURCE_KIND_WIKI,
    GoldExample,
    align_token_char_spans,
    canonical_domain,
    detect_strata,
    is_wikipedia_example,
    load_ezafe_gold,
    resolve_source_kind,
    tokenize_raw,
    utc_now_iso,
    write_ezafe_gold,
)
from persian_seo_normalizer.ezafe_gold_filters import (
    dedupe_template_clusters,
    rejection_reason,
)

UA = "persian-seo-os-ezafe-gold/0.1 (research sampling; contact: local-dev)"

CONTENT_URLS: list[tuple[str, str]] = [
    ("https://www.digikala.com/mag/best-ceramic-cookware-set/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/best-shampoo-for-hair-transplant/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/buy-quarter-coin-or-full-coin/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/baby-girl-gifts-ideas/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/best-birthday-gift-ideas-for-spouse/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/category/buying-guide/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/18th-birthday-gift-ideas-for-girls/", SOURCE_KIND_ECOMMERCE),
    ("https://www.digikala.com/mag/best-gift-ideas-for-baby-naming-ceremony/", SOURCE_KIND_ECOMMERCE),
    ("https://blog.okala.com/", SOURCE_KIND_ECOMMERCE),
    ("https://www.basalam.com/", SOURCE_KIND_ECOMMERCE),
    ("https://www.modiseh.com/women", SOURCE_KIND_ECOMMERCE),
    ("https://www.modiseh.com/men", SOURCE_KIND_ECOMMERCE),
    ("https://emalls.ir/", SOURCE_KIND_ECOMMERCE),
    ("https://digiato.com/", SOURCE_KIND_MAGAZINE),
    ("https://www.zoomit.ir/howto/", SOURCE_KIND_MAGAZINE),
    ("https://www.hamshahrionline.ir/", SOURCE_KIND_NEWS),
]


def _http_get(url: str, *, timeout: int = 25, retries: int = 5) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "text/html"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 503):
                time.sleep(2.5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def _http_get_json(url: str, *, retries: int = 6) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 503):
                time.sleep(3.0 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
    assert last is not None
    raise last


def extract_body_paragraphs(page_html: str) -> list[str]:
    text = re.sub(
        r"(?is)<(script|style|nav|header|footer|aside|form|noscript)[^>]*>.*?</\1>",
        " ",
        page_html,
    )
    chunks = re.findall(r"(?is)<(?:article|main)[^>]*>(.*?)</(?:article|main)>", text)
    scope = " ".join(chunks) if chunks else text
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", scope)
    if not paras:
        paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", text)
    out: list[str] = []
    for p in paras:
        plain = re.sub(r"(?s)<[^>]+>", " ", p)
        plain = html.unescape(plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        if plain:
            out.append(plain)
    return out


def sentences_from_paragraphs(paragraphs: list[str]) -> list[str]:
    sents: list[str] = []
    for para in paragraphs:
        for sent in re.split(r"(?<=[.!?؟۔])\s+", para):
            sent = re.sub(r"\s+", " ", sent).strip()
            if sent:
                sents.append(sent)
    return sents


def _make_example(
    *,
    eid: str,
    text: str,
    source: str,
    source_kind: str,
    source_url: str,
    license_: str,
    collected_at: str,
    page_title: str = "",
    revision_id: str = "",
) -> GoldExample | None:
    if rejection_reason(text) is not None:
        return None
    tokens = tuple(tokenize_raw(text))
    if not (5 <= len(tokens) <= 20):
        return None
    try:
        spans = align_token_char_spans(text, tokens)
    except ValueError:
        return None
    return GoldExample(
        id=eid,
        text=text,
        tokens=tokens,
        char_spans=spans,
        ezafe=None,
        verified=False,
        strata=tuple(detect_strata(text)),
        source=source,
        source_kind=source_kind,
        source_url=source_url,
        license=license_,
        collected_at=collected_at,
        page_title=page_title,
        revision_id=revision_id,
        note="cleaned body sentence; unlabeled",
        tokenizer_source="whitespace_raw",
    )


def filter_existing(
    examples: list[GoldExample],
) -> tuple[list[GoldExample], Counter[str], list[dict]]:
    kept: list[GoldExample] = []
    reasons: Counter[str] = Counter()
    rejected: list[dict] = []
    for ex in examples:
        reason = rejection_reason(ex.text)
        if reason is not None:
            reasons[reason] += 1
            rejected.append(
                {
                    "id": ex.id,
                    "text": ex.text,
                    "reason": reason,
                    "source": ex.source,
                    "source_kind": ex.source_kind,
                }
            )
            continue
        kept.append(ex)
    return kept, reasons, rejected


def harvest_web(
    *,
    limit: int,
    seen_texts: set[str],
) -> tuple[list[GoldExample], Counter[str], list[dict]]:
    collected_at = utc_now_iso()
    out: list[GoldExample] = []
    reasons: Counter[str] = Counter()
    rejected_rows: list[dict] = []
    for url, kind in CONTENT_URLS:
        if len(out) >= limit:
            break
        try:
            page = _http_get(url)
        except (urllib.error.URLError, TimeoutError, UnicodeError) as exc:
            print(f"WARN skip {url}: {exc}", file=sys.stderr)
            continue
        domain = canonical_domain(url)
        for sent in sentences_from_paragraphs(extract_body_paragraphs(page)):
            if sent in seen_texts:
                continue
            reason = rejection_reason(sent)
            if reason is not None:
                reasons[reason] += 1
                if len(rejected_rows) < 400:
                    rejected_rows.append(
                        {"text": sent, "reason": reason, "source_url": url}
                    )
                continue
            ex = _make_example(
                eid=f"web-{domain.split('.')[0]}-{len(out):04d}",
                text=sent,
                source=domain,
                source_kind=resolve_source_kind(
                    source=domain, source_kind=kind, source_url=url
                ),
                source_url=url,
                license_="source-site-terms (snippet for evaluation only)",
                collected_at=collected_at,
            )
            if ex is None:
                reasons["token_or_span_fail"] += 1
                continue
            seen_texts.add(sent)
            out.append(ex)
            if len(out) >= limit:
                break
        time.sleep(0.4)
    return out, reasons, rejected_rows


def harvest_wiki(
    *,
    limit: int,
    seen_texts: set[str],
) -> tuple[list[GoldExample], Counter[str], list[dict]]:
    collected_at = utc_now_iso()
    out: list[GoldExample] = []
    reasons: Counter[str] = Counter()
    rejected_rows: list[dict] = []
    idle_rounds = 0
    while len(out) < limit and idle_rounds < 8:
        before = len(out)
        rnd = _http_get_json(
            "https://fa.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "list": "random",
                    "rnnamespace": 0,
                    "rnlimit": 15,
                    "format": "json",
                }
            )
        )
        titles = [x["title"] for x in rnd.get("query", {}).get("random", [])]
        if not titles:
            break
        info = _http_get_json(
            "https://fa.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "prop": "extracts|info|revisions",
                    "explaintext": 1,
                    "exintro": 0,
                    "exchars": 1500,
                    "rvprop": "ids",
                    "inprop": "url",
                    "titles": "|".join(titles),
                    "format": "json",
                }
            )
        )
        for page in info.get("query", {}).get("pages", {}).values():
            if "extract" not in page:
                continue
            title = page.get("title", "")
            pageid = page.get("pageid", "")
            revs = page.get("revisions") or []
            revid = str(revs[0].get("revid", "")) if revs else ""
            url = page.get("fullurl") or f"https://fa.wikipedia.org/?curid={pageid}"
            for sent in re.split(r"(?<=[.!?؟۔\n])\s+", page["extract"]):
                sent = re.sub(r"\s+", " ", sent).strip()
                if not sent or sent in seen_texts:
                    continue
                reason = rejection_reason(sent)
                if reason is not None:
                    reasons[reason] += 1
                    if len(rejected_rows) < 600:
                        rejected_rows.append(
                            {
                                "text": sent,
                                "reason": reason,
                                "source_url": url,
                                "page_title": title,
                            }
                        )
                    continue
                ex = _make_example(
                    eid=f"wiki-{pageid}-{len(out):04d}",
                    text=sent,
                    source="fa.wikipedia.org",
                    source_kind=SOURCE_KIND_WIKI,
                    source_url=url,
                    license_="CC BY-SA 4.0",
                    collected_at=collected_at,
                    page_title=title,
                    revision_id=revid,
                )
                if ex is None:
                    reasons["token_or_span_fail"] += 1
                    continue
                seen_texts.add(sent)
                out.append(ex)
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
        if len(out) == before:
            idle_rounds += 1
        else:
            idle_rounds = 0
        time.sleep(1.2)
    return out, reasons, rejected_rows


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
        "--report",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_filter_report.json",
    )
    parser.add_argument("--wiki-keep", type=int, default=120)
    parser.add_argument("--web-keep", type=int, default=80)
    parser.add_argument("--no-harvest", action="store_true")
    args = parser.parse_args(argv)
    out_path = args.out or args.gold

    existing = load_ezafe_gold(args.gold, require_labeled=False)
    kept, existing_reasons, existing_rej = filter_existing(existing)
    wiki = [ex for ex in kept if is_wikipedia_example(ex)]
    web = [ex for ex in kept if not is_wikipedia_example(ex)]

    kept_idx, tmpl = dedupe_template_clusters(
        [ex.text for ex in wiki], max_per_cluster=3
    )
    wiki = [wiki[i] for i in kept_idx]

    seen = {ex.text for ex in wiki + web}
    harvest_wiki_reasons: Counter[str] = Counter()
    harvest_web_reasons: Counter[str] = Counter()
    wiki_rej: list[dict] = []
    web_rej: list[dict] = []

    if not args.no_harvest:
        if len(wiki) < args.wiki_keep:
            need = args.wiki_keep - len(wiki) + 40
            print(f"Top-up wiki need≈{need}…", flush=True)
            extra, harvest_wiki_reasons, wiki_rej = harvest_wiki(
                limit=need, seen_texts=seen
            )
            wiki.extend(extra)
            kept_idx, tmpl = dedupe_template_clusters(
                [ex.text for ex in wiki], max_per_cluster=3
            )
            wiki = [wiki[i] for i in kept_idx]
        if len(web) < args.web_keep or sum(
            1 for ex in web if ex.source_kind == SOURCE_KIND_ECOMMERCE
        ) < MIN_ECOMMERCE_TARGET:
            need = max(args.web_keep - len(web), MIN_ECOMMERCE_TARGET) + 30
            print(f"Top-up web need≈{need}…", flush=True)
            extra, harvest_web_reasons, web_rej = harvest_web(
                limit=need, seen_texts=seen
            )
            web.extend(extra)

    wiki_final = wiki[: args.wiki_keep]
    ecom = [ex for ex in web if ex.source_kind == SOURCE_KIND_ECOMMERCE]
    other = [ex for ex in web if ex.source_kind != SOURCE_KIND_ECOMMERCE]
    web_final: list[GoldExample] = []
    # Keep commercial diversity: ecommerce floor, then magazine/news, then more ecom.
    ecom_floor = min(len(ecom), max(MIN_ECOMMERCE_TARGET, args.web_keep // 2))
    web_final.extend(ecom[:ecom_floor])
    for ex in other:
        if len(web_final) >= args.web_keep:
            break
        web_final.append(ex)
    for ex in ecom[ecom_floor:]:
        if len(web_final) >= args.web_keep:
            break
        web_final.append(ex)

    final = wiki_final + web_final
    write_ezafe_gold(out_path, final)

    kind_counts = Counter(ex.source_kind for ex in final)
    ecom_domains = Counter(
        ex.source for ex in final if ex.source_kind == SOURCE_KIND_ECOMMERCE
    )
    report = {
        "existing_rejection_counts": dict(existing_reasons),
        "harvest_wiki_rejection_counts": dict(harvest_wiki_reasons),
        "harvest_web_rejection_counts": dict(harvest_web_reasons),
        "wiki_template": {
            "n_clusters": tmpl.n_clusters,
            "largest_cluster": tmpl.largest_cluster,
            "dropped": tmpl.dropped,
            "kept_after_dedupe": tmpl.n_out,
        },
        "final_n": len(final),
        "final_by_kind": dict(kind_counts),
        "ecommerce_n": kind_counts.get(SOURCE_KIND_ECOMMERCE, 0),
        "ecommerce_domains": dict(ecom_domains),
        "ecommerce_shortfall": max(
            0, MIN_ECOMMERCE_TARGET - kind_counts.get(SOURCE_KIND_ECOMMERCE, 0)
        ),
        "rejected_samples": {
            "existing": existing_rej[:50],
            "wiki_harvest": wiki_rej[:30],
            "web_harvest": web_rej[:30],
        },
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {k: v for k, v in report.items() if k != "rejected_samples"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {len(final)} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
