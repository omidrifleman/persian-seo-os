"""خوشه‌بندی قطعی کلیدواژه فارسی + تشخیص نیت واژگانی.

بدون شبکه، بدون LLM، بدون embedding، بدون تصادف.
سوار بر `keyword_fingerprint` / `keyword_content_tokens` موجود.

کلید خوشه دو بخشی است::

    cluster_id = f\"{topic_core_fingerprint}:{intent}\"

که ``topic_core_fingerprint = keyword_fingerprint(\" \".join(topic_core_tokens))``
و ``topic_core_tokens`` = توکن‌های محتوا منهای فقط نشانگرهای **strippable**
آتش‌گرفته (و منهای استاپ‌وردهای سئو که ``keyword_content_tokens`` حذف می‌کند).
نشانگرهای غیرstrippable نیت می‌سازند ولی در هسته می‌مانند.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from .fingerprint import keyword_content_tokens, keyword_fingerprint
from .normalize import analyze_form

SearchDemandStatus = Literal["known", "estimated", "unknown"]
SearchIntent = Literal[
    "transactional",
    "commercial",
    "informational",
    "navigational",
    "unknown",
]

_INTENT_PRIORITY: tuple[SearchIntent, ...] = (
    "transactional",
    "commercial",
    "informational",
    "navigational",
)

_DEMAND_STATUS_RANK = {"known": 2, "estimated": 1, "unknown": 0}


@dataclass(frozen=True)
class _MarkerSpec:
    surface: str
    intent: SearchIntent
    strippable: bool


# نشانگرها: مطابقت روی analyze_form با مرز توکن، پویش چپ‌به‌راست + مصرف موقعیت،
# در هر موقعیت طولانی‌تر اول. strippable=False یعنی نیت می‌سازد ولی از هسته حذف نمی‌شود.
# منبع: ADR-0010 — نه API بیرونی.
_MARKER_SPECS: tuple[_MarkerSpec, ...] = (
    # transactional — همگی strippable
    _MarkerSpec("قیمت خرید", "transactional", True),
    _MarkerSpec("ثبت نام", "transactional", True),
    _MarkerSpec("ثبت‌نام", "transactional", True),
    _MarkerSpec("خرید", "transactional", True),
    _MarkerSpec("سفارش", "transactional", True),
    _MarkerSpec("دانلود", "transactional", True),
    _MarkerSpec("دریافت", "transactional", True),
    _MarkerSpec("رزرو", "transactional", True),
    _MarkerSpec("پرداخت", "transactional", True),
    # commercial
    _MarkerSpec("ارزان ترین", "commercial", True),
    _MarkerSpec("ارزان‌ترین", "commercial", True),
    _MarkerSpec("بهترین", "commercial", True),
    _MarkerSpec("مقایسه", "commercial", True),
    _MarkerSpec("تخفیف", "commercial", True),
    _MarkerSpec("قیمت", "commercial", True),
    _MarkerSpec("ارزان", "commercial", True),
    _MarkerSpec("گران", "commercial", True),
    _MarkerSpec("فروشگاه", "commercial", False),
    _MarkerSpec("نمایندگی", "commercial", False),
    _MarkerSpec("فروش", "commercial", False),
    # informational («بررسی» محتوایی است، نه commercial)
    _MarkerSpec("چگونه", "informational", True),
    _MarkerSpec("چطور", "informational", True),
    _MarkerSpec("آموزش", "informational", True),
    _MarkerSpec("راهنما", "informational", True),
    _MarkerSpec("معنی", "informational", True),
    _MarkerSpec("تعریف", "informational", True),
    _MarkerSpec("تفاوت", "informational", True),
    _MarkerSpec("فرق", "informational", True),
    _MarkerSpec("چیست", "informational", True),
    _MarkerSpec("کیست", "informational", True),
    _MarkerSpec("چرا", "informational", True),
    _MarkerSpec("بررسی", "informational", False),
    _MarkerSpec("نمونه", "informational", False),
    _MarkerSpec("مثال", "informational", False),
    # navigational
    _MarkerSpec("ورود", "navigational", True),
    _MarkerSpec("سایت", "navigational", False),
    _MarkerSpec("رسمی", "navigational", False),
    _MarkerSpec("اپلیکیشن", "navigational", False),
    _MarkerSpec("اپ", "navigational", False),
    _MarkerSpec("تلگرام", "navigational", False),
    _MarkerSpec("اینستاگرام", "navigational", False),
)


@dataclass(frozen=True)
class KeywordInput:
    keyword_id: str
    text: str
    search_demand: int | None = None
    search_demand_status: SearchDemandStatus = "unknown"
    locale: str = "fa-IR"


@dataclass(frozen=True)
class KeywordRecord:
    keyword_id: str
    text: str
    fingerprint: str
    content_tokens: tuple[str, ...]
    topic_core_tokens: tuple[str, ...]
    topic_core_fingerprint: str
    intent: SearchIntent
    intent_markers: tuple[str, ...]
    intent_reason_codes: tuple[str, ...]
    competing_intent_categories: tuple[SearchIntent, ...]
    search_demand: int | None
    search_demand_status: SearchDemandStatus


@dataclass(frozen=True)
class KeywordCluster:
    cluster_id: str
    topic_core_fingerprint: str
    intent: SearchIntent
    head_keyword_id: str
    head_text: str
    members: tuple[KeywordRecord, ...]
    head_decided_by: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SkippedKeyword:
    keyword_id: str
    text: str
    reason_code: str
    reason_fa: str


@dataclass(frozen=True)
class ClusterResult:
    clusters: tuple[KeywordCluster, ...]
    skipped: tuple[SkippedKeyword, ...]


def _marker_catalog() -> list[tuple[str, SearchIntent, tuple[str, ...], bool]]:
    """(surface, intent, analyzed_tokens, strippable) sorted longest-first.

    Duplicate analyzed forms (e.g. «ارزان‌ترین» vs «ارزان ترین») collapse to one row.
    """
    rows: list[tuple[str, SearchIntent, tuple[str, ...], bool]] = []
    for spec in _MARKER_SPECS:
        toks = tuple(analyze_form(spec.surface).split())
        if toks:
            rows.append((spec.surface, spec.intent, toks, spec.strippable))
    rows.sort(key=lambda r: (-len(r[2]), -len(r[0]), r[0]))
    deduped: list[tuple[str, SearchIntent, tuple[str, ...], bool]] = []
    seen_toks: set[tuple[str, ...]] = set()
    for row in rows:
        if row[2] in seen_toks:
            continue
        seen_toks.add(row[2])
        deduped.append(row)
    return deduped


_MARKER_CATALOG = _marker_catalog()
_STRIPPABLE_BY_SURFACE = {s: strip for s, _, _, strip in _MARKER_CATALOG}


def _find_intent_markers(
    analyzed: str,
) -> list[tuple[str, SearchIntent, bool]]:
    """Left-to-right greedy match; consume token spans so overlaps cannot re-fire."""
    tokens = analyzed.split()
    n_tok = len(tokens)
    consumed = [False] * n_tok
    fired: list[tuple[str, SearchIntent, bool]] = []
    i = 0
    while i < n_tok:
        if consumed[i]:
            i += 1
            continue
        matched = False
        for surface, intent, mt, strippable in _MARKER_CATALOG:
            n = len(mt)
            end = i + n
            if end > n_tok:
                continue
            if any(consumed[j] for j in range(i, end)):
                continue
            if tuple(tokens[i:end]) == mt:
                fired.append((surface, intent, strippable))
                for j in range(i, end):
                    consumed[j] = True
                matched = True
                i = end
                break
        if not matched:
            i += 1
    return fired


def detect_search_intent(text: str) -> tuple[
    SearchIntent,
    tuple[str, ...],
    tuple[str, ...],
    tuple[SearchIntent, ...],
]:
    """Return intent, markers, reason_codes, competing categories (all fired)."""
    analyzed = analyze_form(text)
    fired = _find_intent_markers(analyzed)
    if not fired:
        return "unknown", (), ("intent_unknown",), ()

    markers = tuple(m for m, _, _ in fired)
    fired_set = {intent for _, intent, _ in fired}
    categories = tuple(c for c in _INTENT_PRIORITY if c in fired_set)
    reason_codes: list[str] = [f"intent_{c}" for c in categories]

    if len(categories) == 1:
        return categories[0], markers, tuple(reason_codes), ()

    reason_codes.append("multiple_intent_categories")
    chosen = categories[0]
    return chosen, markers, tuple(reason_codes), categories


def topic_core_tokens_for(text: str, intent_markers: tuple[str, ...]) -> list[str]:
    """Content tokens minus tokens of *strippable* fired markers only."""
    remaining = list(keyword_content_tokens(text))
    for surface in intent_markers:
        if not _STRIPPABLE_BY_SURFACE.get(surface, True):
            continue
        for tok in keyword_content_tokens(surface):
            if tok in remaining:
                remaining.remove(tok)
    return remaining


def make_cluster_id(topic_core_fingerprint: str, intent: SearchIntent) -> str:
    """پایدار: ``f\"{topic_core_fingerprint}:{intent}\"``."""
    return f"{topic_core_fingerprint}:{intent}"


def _head_key_for_max(rec: KeywordRecord) -> tuple:
    """Higher tuple wins."""
    status_rank = _DEMAND_STATUS_RANK[rec.search_demand_status]
    if rec.search_demand_status == "unknown":
        demand_val = -(10**18)
    else:
        demand_val = rec.search_demand if rec.search_demand is not None else -(10**18)
    return (
        status_rank,
        demand_val,
        -len(rec.content_tokens),
        -len(rec.text.strip()),
    )


def _decided_by_head(head: KeywordRecord, members: list[KeywordRecord]) -> str:
    others = [m for m in members if m.keyword_id != head.keyword_id]
    if not others:
        return "singleton"
    best_key = None
    cands: list[KeywordRecord] = []
    for rec in others:
        key = _head_key_for_max(rec)
        if best_key is None or key > best_key:
            best_key = key
            cands = [rec]
        elif key == best_key:
            cands.append(rec)
    runner = min(cands, key=lambda r: r.keyword_id)
    names = (
        "search_demand_status",
        "search_demand",
        "shorter_content_tokens",
        "shorter_surface",
    )
    hk = _head_key_for_max(head)
    rk = _head_key_for_max(runner)
    for name, hv, rv in zip(names, hk, rk, strict=True):
        if hv != rv:
            return name
    return "keyword_id_tiebreak"


def _pick_head(members: list[KeywordRecord]) -> tuple[KeywordRecord, str]:
    best_key = None
    cands: list[KeywordRecord] = []
    for rec in members:
        key = _head_key_for_max(rec)
        if best_key is None or key > best_key:
            best_key = key
            cands = [rec]
        elif key == best_key:
            cands.append(rec)
    head = min(cands, key=lambda r: r.keyword_id)
    return head, _decided_by_head(head, members)


def _cluster_reason_codes(
    ordered: list[KeywordRecord], *, singleton: bool
) -> tuple[str, ...]:
    """Union of all members' intent_reason_codes (head-first), then cluster-only flags."""
    seen: set[str] = set()
    codes: list[str] = []
    for rec in ordered:
        for c in rec.intent_reason_codes:
            if c not in seen:
                seen.add(c)
                codes.append(c)
    if singleton:
        codes.append("singleton_cluster")
    return tuple(codes)


def cluster_keywords(
    keywords: list[KeywordInput],
    *,
    order_sensitive: bool = False,
) -> ClusterResult:
    """خوشه‌بندی قطعی روی (topic_core_fingerprint, intent).

    ``order_sensitive`` فقط به ``keyword_fingerprint`` هستهٔ موضوع پاس داده می‌شود
    (پیش‌فرض False طبق ADR-0010).

    ``cluster_id = f\"{topic_core_fingerprint}:{intent}\"``.
    """
    skipped: list[SkippedKeyword] = []
    seen_ids: set[str] = set()
    records: list[KeywordRecord] = []

    for item in keywords:
        kid = (item.keyword_id or "").strip()
        text = item.text if item.text is not None else ""
        if not kid:
            skipped.append(
                SkippedKeyword(
                    keyword_id=item.keyword_id or "",
                    text=text,
                    reason_code="empty_keyword_id",
                    reason_fa="شناسهٔ کلیدواژه خالی است.",
                )
            )
            continue
        if kid in seen_ids:
            skipped.append(
                SkippedKeyword(
                    keyword_id=kid,
                    text=text,
                    reason_code="duplicate_keyword_id",
                    reason_fa="شناسهٔ کلیدواژه تکراری است؛ فقط نخستین نگه داشته شد.",
                )
            )
            continue
        seen_ids.add(kid)

        if not str(text).strip():
            skipped.append(
                SkippedKeyword(
                    keyword_id=kid,
                    text=text,
                    reason_code="empty_keyword_text",
                    reason_fa="متن کلیدواژه خالی است.",
                )
            )
            continue

        status = item.search_demand_status
        if status not in _DEMAND_STATUS_RANK:
            skipped.append(
                SkippedKeyword(
                    keyword_id=kid,
                    text=text,
                    reason_code="invalid_demand_status",
                    reason_fa=f"وضعیت حجم نامعتبر: {status!r}.",
                )
            )
            continue
        if status == "unknown" and item.search_demand is not None:
            skipped.append(
                SkippedKeyword(
                    keyword_id=kid,
                    text=text,
                    reason_code="demand_status_conflict",
                    reason_fa="با status=unknown نباید search_demand عددی باشد.",
                )
            )
            continue
        if status in ("known", "estimated"):
            if item.search_demand is None:
                skipped.append(
                    SkippedKeyword(
                        keyword_id=kid,
                        text=text,
                        reason_code="missing_search_demand",
                        reason_fa="status شناخته‌شده/تخمینی نیاز به search_demand دارد.",
                    )
                )
                continue
            if item.search_demand < 0:
                skipped.append(
                    SkippedKeyword(
                        keyword_id=kid,
                        text=text,
                        reason_code="negative_search_demand",
                        reason_fa="search_demand منفی مجاز نیست (۰ با known معتبر است).",
                    )
                )
                continue

        content = tuple(keyword_content_tokens(text))
        if not content:
            skipped.append(
                SkippedKeyword(
                    keyword_id=kid,
                    text=text,
                    reason_code="no_content_tokens",
                    reason_fa="پس از حذف استاپ‌ورد توکن محتوایی نماند.",
                )
            )
            continue

        intent, markers, intent_codes, competing = detect_search_intent(text)
        core = topic_core_tokens_for(text, markers)
        if not core:
            skipped.append(
                SkippedKeyword(
                    keyword_id=kid,
                    text=text,
                    reason_code="only_intent_markers",
                    reason_fa="پس از حذف نشانگر نیت توکن موضوعی نماند.",
                )
            )
            continue

        core_fp = keyword_fingerprint(
            " ".join(core), order_sensitive=order_sensitive
        )
        full_fp = keyword_fingerprint(text, order_sensitive=order_sensitive)
        records.append(
            KeywordRecord(
                keyword_id=kid,
                text=text,
                fingerprint=full_fp,
                content_tokens=content,
                topic_core_tokens=tuple(core),
                topic_core_fingerprint=core_fp,
                intent=intent,
                intent_markers=markers,
                intent_reason_codes=intent_codes,
                competing_intent_categories=competing,
                search_demand=item.search_demand,
                search_demand_status=status,
            )
        )

    by_key: dict[tuple[str, SearchIntent], list[KeywordRecord]] = defaultdict(list)
    for rec in records:
        by_key[(rec.topic_core_fingerprint, rec.intent)].append(rec)

    clusters: list[KeywordCluster] = []
    for (core_fp, intent), members in sorted(
        by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])
    ):
        head, decided = _pick_head(members)
        ordered = [head] + sorted(
            [m for m in members if m.keyword_id != head.keyword_id],
            key=lambda m: m.keyword_id,
        )
        clusters.append(
            KeywordCluster(
                cluster_id=make_cluster_id(core_fp, intent),
                topic_core_fingerprint=core_fp,
                intent=intent,
                head_keyword_id=head.keyword_id,
                head_text=head.text,
                members=tuple(ordered),
                head_decided_by=decided,
                reason_codes=_cluster_reason_codes(
                    ordered, singleton=len(members) == 1
                ),
            )
        )

    return ClusterResult(
        clusters=tuple(clusters),
        skipped=tuple(
            sorted(
                skipped,
                key=lambda s: (s.keyword_id, s.reason_code, s.text),
            )
        ),
    )
