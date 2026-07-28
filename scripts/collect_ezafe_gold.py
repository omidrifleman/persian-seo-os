"""One-time offline-prep sampler for ezafe gold candidates (network OK here only).

Writes data/gold/ezafe_gold.jsonl with unlabeled rows (ezafe=null, verified=false).
Never calls detect_ezafe. Tests must not import/run this module against the network.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.ezafe_gold import (
    GoldExample,
    assign_strata_quotas,
    detect_strata,
    load_ezafe_gold,
    tokenize_raw,
    utc_now_iso,
    whitespace_word_count,
    write_ezafe_gold,
)

UA = "persian-seo-os-ezafe-gold/0.1 (research sampling; contact: local-dev)"


def _http_get_json(url: str, *, timeout: int = 30, retries: int = 6) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 503):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def _http_get_text(url: str, *, timeout: int = 30, retries: int = 4) -> str:
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
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


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
    # Must be mostly Persian letters.
    letters = re.findall(r"[\u0600-\u06FF]", sentence)
    return len(letters) >= 8


def fetch_wikipedia_fa(limit: int = 250) -> list[GoldExample]:
    """Sample sentences from Persian Wikipedia (CC BY-SA 4.0)."""
    collected_at = utc_now_iso()
    out: list[GoldExample] = []
    seen_text: set[str] = set()
    # Random pages in batches.
    while len(out) < limit:
        rnd = _http_get_json(
            "https://fa.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "list": "random",
                    "rnnamespace": 0,
                    "rnlimit": 20,
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
                    "exintro": 1,
                    "rvprop": "ids",
                    "inprop": "url",
                    "titles": "|".join(titles),
                    "format": "json",
                }
            )
        )
        pages = info.get("query", {}).get("pages", {})
        for page in pages.values():
            if "extract" not in page or page.get("missing") is not None:
                continue
            title = page.get("title", "")
            pageid = page.get("pageid", "")
            revs = page.get("revisions") or []
            revid = str(revs[0].get("revid", "")) if revs else ""
            url = page.get("fullurl") or (
                f"https://fa.wikipedia.org/?curid={pageid}" if pageid else ""
            )
            extract = page["extract"]
            for sent in re.split(r"(?<=[.!?؟۔\n])\s+", extract):
                sent = re.sub(r"\s+", " ", sent).strip()
                if not _candidate_ok(sent) or sent in seen_text:
                    continue
                seen_text.add(sent)
                tokens = tokenize_raw(sent)
                if not (5 <= len(tokens) <= 15):
                    continue
                strata = detect_strata(sent)
                eid = f"wiki-{pageid}-{len(out):04d}"
                out.append(
                    GoldExample(
                        id=eid,
                        text=sent,
                        tokens=tuple(tokens),
                        ezafe=None,
                        verified=False,
                        strata=tuple(strata),
                        source="fa.wikipedia",
                        source_url=url,
                        license="CC BY-SA 4.0",
                        collected_at=collected_at,
                        page_title=title,
                        revision_id=revid,
                        note="unlabeled candidate; blind human labeling required",
                    )
                )
                if len(out) >= limit:
                    break
        time.sleep(1.0)
        if not titles:
            break
    return out


# Curated public pages for shop/blog-like Persian prose (one-time harvest).
# No Wikipedia here — wiki quota is separate (CC BY-SA).
SHOP_BLOG_URLS = [
    ("https://www.digikala.com/mag/", "shop_mag"),
    ("https://www.digikala.com/mag/category/howto/", "shop_mag"),
    ("https://www.digikala.com/mag/category/shopping-guides/", "shop_mag"),
    ("https://www.digikala.com/mag/category/tech/", "shop_mag"),
    ("https://www.zoomit.ir/", "blog_portal"),
    ("https://www.zoomit.ir/mobile/", "blog_portal"),
    ("https://www.zoomit.ir/howto/", "blog_portal"),
    ("https://digiato.com/", "blog_portal"),
    ("https://digiato.com/digiato/category/mobile/", "blog_portal"),
    ("https://www.tarafdari.com/", "blog_portal"),
    ("https://www.technolife.ir/blog", "shop_mag"),
    ("https://www.technolife.com/blog", "shop_mag"),
    ("https://blog.okala.com/", "shop_mag"),
    ("https://www.basalam.com/blog", "shop_mag"),
    ("https://www.hamshahrionline.ir/", "news_portal"),
    ("https://www.isna.ir/", "news_portal"),
    ("https://www.khabaronline.ir/", "news_portal"),
    ("https://www.zoomg.ir/", "blog_portal"),
    ("https://www.chetor.com/", "blog_portal"),
    ("https://www.sid.ir/blog", "blog_portal"),
]


def fetch_shop_blog(limit: int = 160) -> list[GoldExample]:
    """Harvest short sentences from public HTML pages; record URL + timestamp."""
    collected_at = utc_now_iso()
    out: list[GoldExample] = []
    seen: set[str] = set()
    for url, kind in SHOP_BLOG_URLS:
        if len(out) >= limit:
            break
        try:
            html_text = _http_get_text(url)
        except (urllib.error.URLError, TimeoutError, UnicodeError) as exc:
            print(f"WARN skip {url}: {exc}", file=sys.stderr)
            continue
        text = _strip_html(html_text)
        # Prefer Persian sentence chunks.
        for sent in re.split(r"(?<=[.!?؟۔\n])\s+", text):
            sent = re.sub(r"\s+", " ", sent).strip()
            if len(sent) > 220:
                continue
            if not _candidate_ok(sent) or sent in seen:
                continue
            # Drop nav chrome-ish lines.
            if re.search(
                r"ورود|ثبت[\s‌]?نام|سبد خرید|اپلیکیشن|دانلود|کپی‌رایت|Copyright",
                sent,
                re.IGNORECASE,
            ):
                continue
            seen.add(sent)
            tokens = tokenize_raw(sent)
            if not (5 <= len(tokens) <= 15):
                continue
            strata = detect_strata(sent)
            eid = f"web-{len(out):04d}"
            out.append(
                GoldExample(
                    id=eid,
                    text=sent,
                    tokens=tuple(tokens),
                    ezafe=None,
                    verified=False,
                    strata=tuple(strata),
                    source=kind,
                    source_url=url,
                    license="source-site-terms (snippet for evaluation only)",
                    collected_at=collected_at,
                    note="unlabeled candidate; blind human labeling required",
                )
            )
            if len(out) >= limit:
                break
        time.sleep(0.5)
    return out


def select_corpus(
    wiki: list[GoldExample],
    web: list[GoldExample],
    *,
    n_wiki: int = 120,
    n_web: int = 80,
) -> tuple[list[GoldExample], dict]:
    """Select up to n_wiki + n_web with strata coverage; do not invent sentences."""
    wiki_sel = wiki[:n_wiki]
    web_sel = web[:n_web]
    # Re-balance strata across the combined pool (greedy), then top up to 200
    # preferring already-selected source quotas.
    pool = wiki_sel + web_sel
    # Expand pool if needed from leftovers.
    leftovers = wiki[n_wiki:] + web[n_web:]
    strata_selected, filled, _shortfalls = assign_strata_quotas(pool + leftovers)
    # Add wiki/web to reach counts without inventing.
    final: list[GoldExample] = []
    wiki_count = 0
    web_count = 0

    def is_wiki(ex: GoldExample) -> bool:
        return ex.source == "fa.wikipedia"

    # First take strata-selected, respecting caps.
    for ex in strata_selected:
        if is_wiki(ex) and wiki_count >= n_wiki:
            continue
        if (not is_wiki(ex)) and web_count >= n_web:
            continue
        final.append(ex)
        if is_wiki(ex):
            wiki_count += 1
        else:
            web_count += 1

    def top_up(candidates: list[GoldExample], *, want: int, wiki: bool) -> None:
        nonlocal wiki_count, web_count
        have = wiki_count if wiki else web_count
        for ex in candidates:
            if have >= want:
                break
            if ex.id in {x.id for x in final}:
                continue
            if wiki and not is_wiki(ex):
                continue
            if (not wiki) and is_wiki(ex):
                continue
            final.append(ex)
            have += 1
            if wiki:
                wiki_count = have
            else:
                web_count = have

    top_up(wiki, want=n_wiki, wiki=True)
    top_up(web, want=n_web, wiki=False)

    # Recompute filled strata on final.
    filled_final = {k: 0 for k in filled}
    for ex in final:
        for s in ex.strata:
            if s in filled_final:
                filled_final[s] += 1
    shortfalls_final = {
        k: max(0, v - filled_final.get(k, 0))
        for k, v in {
            "zwnj": 30,
            "plural_ha": 30,
            "ye_non_ezafe": 25,
            "no_ezafe_candidate": 25,
            "latin_brand": 20,
            "number_unit": 20,
        }.items()
    }
    report = {
        "wiki_available": len(wiki),
        "web_available": len(web),
        "wiki_selected": sum(1 for ex in final if is_wiki(ex)),
        "web_selected": sum(1 for ex in final if not is_wiki(ex)),
        "total_selected": len(final),
        "strata_filled": filled_final,
        "strata_shortfalls": shortfalls_final,
    }
    return final, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "gold" / "ezafe_gold.jsonl",
    )
    parser.add_argument("--wiki-pool", type=int, default=300)
    parser.add_argument("--web-pool", type=int, default=200)
    parser.add_argument(
        "--reuse-wiki-from",
        type=Path,
        default=None,
        help="Reuse fa.wikipedia rows from an existing JSONL (avoid API rate limits).",
    )
    args = parser.parse_args(argv)

    if args.reuse_wiki_from:
        print(f"Reusing Wikipedia rows from {args.reuse_wiki_from}…", flush=True)
        wiki = [
            ex
            for ex in load_ezafe_gold(args.reuse_wiki_from, require_labeled=False)
            if ex.source == "fa.wikipedia"
        ]
    else:
        print("Fetching Wikipedia FA…", flush=True)
        wiki = fetch_wikipedia_fa(limit=args.wiki_pool)
    print(f"wiki pool={len(wiki)}", flush=True)
    print("Fetching shop/blog HTML…", flush=True)
    web = fetch_shop_blog(limit=args.web_pool)
    print(f"web pool={len(web)}", flush=True)
    selected, report = select_corpus(wiki, web)
    write_ezafe_gold(args.out, selected)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(report["strata_shortfalls"].values()):
        print("STRATA_SHORTFALLS present — no invented sentences.", flush=True)
    if report["wiki_selected"] < 120 or report["web_selected"] < 80:
        print(
            f"SOURCE_SHORTFALL wiki={report['wiki_selected']}/120 "
            f"web={report['web_selected']}/80",
            flush=True,
        )
    print(f"Wrote {len(selected)} rows -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
