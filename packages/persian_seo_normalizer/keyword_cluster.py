"""خوشه‌بندی قطعی کلیدواژه فارسی + تشخیص نیت واژگانی.

بدون شبکه، بدون LLM، بدون embedding، بدون تصادف.
سوار بر `keyword_fingerprint` / `keyword_content_tokens` موجود.

کلید خوشه دو بخشی است::

    cluster_id = f\"{topic_core_fingerprint}:{intent}\"

که ``topic_core_fingerprint = keyword_fingerprint(\" \".join(topic_core_tokens))``
و ``topic_core_tokens`` از حذف مشروط نشانگرها به دست می‌آید (ADR-0010).
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

_HEAD_CRITERION_NAMES = (
    "search_demand_status",
    "search_demand",
    "shorter_content_tokens",
    "shorter_normalized_surface",
    "keyword_id_tiebreak",
)

# پس از حذف نشانگر، اگر فقط این توکن‌ها بمانند هسته موضوعی شمرده نمی‌شود
# و نشانگرها به هسته برمی‌گردند (مثلاً «فروشگاه اینترنتی»). ADR-0010.
_INSUFFICIENT_CORE_TOKENS = frozenset({"اینترنتی"})


@dataclass(frozen=True)
class FiredIntentMarker:
    """نشانگر نیت آتش‌گرفته با موقعیت شروع در توکن‌های analyze_form."""

    surface: str
    intent: SearchIntent
    token_start: int


@dataclass(frozen=True)
class _MarkerSpec:
    surface: str
    intent: SearchIntent


# نشانگرها: مطابقت روی analyze_form با مرز توکن، پویش چپ‌به‌راست + مصرف موقعیت،
# در هر موقعیت طولانی‌تر اول. منبع: ADR-0010 — نه API بیرونی.
_MARKER_SPECS: tuple[_MarkerSpec, ...] = (
    # transactional
    _MarkerSpec("قیمت خرید", "transactional"),
    _MarkerSpec("ثبت نام", "transactional"),
    _MarkerSpec("ثبت‌نام", "transactional"),
    _MarkerSpec("خرید", "transactional"),
    _MarkerSpec("سفارش", "transactional"),
    _MarkerSpec("دانلود", "transactional"),
    _MarkerSpec("دریافت", "transactional"),
    _MarkerSpec("رزرو", "transactional"),
    _MarkerSpec("پرداخت", "transactional"),
    # commercial
    _MarkerSpec("ارزان ترین", "commercial"),
    _MarkerSpec("ارزان‌ترین", "commercial"),
    _MarkerSpec("بهترین", "commercial"),
    _MarkerSpec("مقایسه", "commercial"),
    _MarkerSpec("تخفیف", "commercial"),
    _MarkerSpec("قیمت", "commercial"),
    _MarkerSpec("ارزان", "commercial"),
    _MarkerSpec("گران", "commercial"),
    _MarkerSpec("فروشگاه", "commercial"),
    _MarkerSpec("نمایندگی", "commercial"),
    _MarkerSpec("فروش", "commercial"),
    # informational
    _MarkerSpec("چگونه", "informational"),
    _MarkerSpec("چطور", "informational"),
    _MarkerSpec("آموزش", "informational"),
    _MarkerSpec("راهنما", "informational"),
    _MarkerSpec("معنی", "informational"),
    _MarkerSpec("تعریف", "informational"),
    _MarkerSpec("تفاوت", "informational"),
    _MarkerSpec("فرق", "informational"),
    _MarkerSpec("چیست", "informational"),
    _MarkerSpec("کیست", "informational"),
    _MarkerSpec("چرا", "informational"),
    _MarkerSpec("بررسی", "informational"),
    _MarkerSpec("نمونه", "informational"),
    _MarkerSpec("مثال", "informational"),
    # navigational — فقط الگوی واقعی ورود/ناوبری
    _MarkerSpec("ورود به سایت", "navigational"),
    _MarkerSpec("سایت رسمی", "navigational"),
    _MarkerSpec("پنل کاربری", "navigational"),
    _MarkerSpec("ورود", "navigational"),
    _MarkerSpec("لاگین", "navigational"),
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
    intent_markers: tuple[FiredIntentMarker, ...]
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


def _build_marker_catalog(
    specs: tuple[_MarkerSpec, ...],
) -> list[tuple[str, SearchIntent, tuple[str, ...]]]:
    """(surface, intent, analyzed_tokens) sorted longest-first.

    Duplicate analyzed forms with identical intent collapse to one row.
    Conflicting intent for the same tokens raises ValueError.
    """
    rows: list[tuple[str, SearchIntent, tuple[str, ...]]] = []
    for spec in specs:
        toks = tuple(analyze_form(spec.surface).split())
        if toks:
            rows.append((spec.surface, spec.intent, toks))
    rows.sort(key=lambda r: (-len(r[2]), -len(r[0]), r[0]))
    deduped: list[tuple[str, SearchIntent, tuple[str, ...]]] = []
    seen: dict[tuple[str, ...], tuple[SearchIntent, str]] = {}
    for surface, intent, toks in rows:
        prev = seen.get(toks)
        if prev is not None:
            prev_intent, prev_surface = prev
            if prev_intent != intent:
                raise ValueError(
                    "marker catalog conflict: identical analyze tokens "
                    f"{toks!r} with differing intent "
                    f"({prev_surface!r}/{prev_intent} vs {surface!r}/{intent})"
                )
            continue
        seen[toks] = (intent, surface)
        deduped.append((surface, intent, toks))
    return deduped


def _marker_catalog() -> list[tuple[str, SearchIntent, tuple[str, ...]]]:
    return _build_marker_catalog(_MARKER_SPECS)


_MARKER_CATALOG = _marker_catalog()


def _find_intent_markers(analyzed: str) -> list[FiredIntentMarker]:
    """Left-to-right greedy match; consume token spans so overlaps cannot re-fire."""
    tokens = analyzed.split()
    n_tok = len(tokens)
    consumed = [False] * n_tok
    fired: list[FiredIntentMarker] = []
    i = 0
    while i < n_tok:
        if consumed[i]:
            i += 1
            continue
        matched = False
        for surface, intent, mt in _MARKER_CATALOG:
            n = len(mt)
            end = i + n
            if end > n_tok:
                continue
            if any(consumed[j] for j in range(i, end)):
                continue
            if tuple(tokens[i:end]) == mt:
                fired.append(
                    FiredIntentMarker(
                        surface=surface, intent=intent, token_start=i
                    )
                )
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
    tuple[FiredIntentMarker, ...],
    tuple[str, ...],
    tuple[SearchIntent, ...],
]:
    """Return intent, fired markers, reason_codes, competing categories."""
    analyzed = analyze_form(text)
    fired = tuple(_find_intent_markers(analyzed))
    if not fired:
        return "unknown", (), ("intent_unknown",), ()

    fired_set = {m.intent for m in fired}
    categories = tuple(c for c in _INTENT_PRIORITY if c in fired_set)
    reason_codes: list[str] = [f"intent_{c}" for c in categories]

    if len(categories) == 1:
        return categories[0], fired, tuple(reason_codes), ()

    reason_codes.append("multiple_intent_categories")

    info_starts = [m.token_start for m in fired if m.intent == "informational"]
    trans_starts = [m.token_start for m in fired if m.intent == "transactional"]
    if (
        info_starts
        and trans_starts
        and min(info_starts) < min(trans_starts)
    ):
        reason_codes.append("informational_precedes_transactional")
        return "informational", fired, tuple(reason_codes), categories

    chosen = categories[0]
    return chosen, fired, tuple(reason_codes), categories


def _strip_marker_tokens(
    content: list[str], fired_markers: tuple[FiredIntentMarker, ...]
) -> list[str]:
    remaining = list(content)
    for marker in fired_markers:
        for tok in keyword_content_tokens(marker.surface):
            if tok in remaining:
                remaining.remove(tok)
    return remaining


def _core_is_usable(tokens: list[str]) -> bool:
    if not tokens:
        return False
    return not all(t in _INSUFFICIENT_CORE_TOKENS for t in tokens)


def topic_core_tokens_for(
    text: str, fired_markers: tuple[FiredIntentMarker, ...]
) -> list[str]:
    """حذف مشروط نشانگرها از توکن‌های محتوا.

    همیشه حذف کن؛ اگر باقی‌مانده خالی بود → [] (caller: only_intent_markers).
    اگر باقی‌مانده فقط توکن‌های ناکافی بود → کل محتوا را هسته بگیر
    (نشانگرها برمی‌گردند؛ مثلاً فروشگاه + اینترنتی).
    """
    content = keyword_content_tokens(text)
    stripped = _strip_marker_tokens(content, fired_markers)
    if _core_is_usable(stripped):
        return stripped
    if not stripped:
        return []
    return list(content)


def make_cluster_id(topic_core_fingerprint: str, intent: SearchIntent) -> str:
    """پایدار: ``f\"{topic_core_fingerprint}:{intent}\"``."""
    return f"{topic_core_fingerprint}:{intent}"


def _member_rank_key(rec: KeywordRecord) -> tuple:
    """Ascending sort key: first element is the head."""
    status_rank = _DEMAND_STATUS_RANK[rec.search_demand_status]
    if rec.search_demand_status == "unknown":
        demand_val = -(10**18)
    else:
        demand_val = rec.search_demand if rec.search_demand is not None else -(10**18)
    return (
        -status_rank,
        -demand_val,
        len(rec.content_tokens),
        len(analyze_form(rec.text)),
        rec.keyword_id,
    )


def _rank_members(members: list[KeywordRecord]) -> list[KeywordRecord]:
    return sorted(members, key=_member_rank_key)


def _pick_head(members: list[KeywordRecord]) -> tuple[KeywordRecord, str]:
    ranked = _rank_members(members)
    head = ranked[0]
    if len(ranked) == 1:
        return head, "singleton"
    runner = ranked[1]
    hk = _member_rank_key(head)
    rk = _member_rank_key(runner)
    for name, hv, rv in zip(_HEAD_CRITERION_NAMES, hk, rk, strict=True):
        if hv != rv:
            return head, name
    return head, "keyword_id_tiebreak"


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
