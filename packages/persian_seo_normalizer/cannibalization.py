"""تشخیص تصادم کیورد اعلام‌شده (declared-keyword collision).

محدودیت: فقط صفحاتی که target_keyword اعلام کرده‌اند و fingerprint یکسان دارند.
کانیبالیزیشن واقعی روی کیورد اعلام‌نشده فقط با GSC در برش بعدی است.
بدون شبکه/کراول — ورودی را صداکننده می‌دهد.
"""
from __future__ import annotations

from dataclasses import dataclass

from .fingerprint import keyword_content_tokens, keyword_fingerprint
from .normalize import analyze_form

SIGNIFICANT_WORD_COUNT = 500

_ROLE_RANK = {
    "pillar": 3,
    "commercial": 2,
    "informational": 1,
    "other": 0,
}

_ACTIONS = frozenset({"keep", "consolidate_into", "retarget", "differentiate"})


@dataclass(frozen=True)
class PageTarget:
    """یک صفحه با کیورد اعلام‌شده — همه سیگنال‌ها از ورودی می‌آیند."""

    page_id: str
    url: str
    title: str
    h1: str
    target_keyword: str
    priority: int | None = None
    page_role: str = "other"
    word_count: int = 0
    inbound_internal_links: int = 0


@dataclass(frozen=True)
class SkippedPage:
    page_id: str
    url: str
    reason_code: str
    reason_fa: str


@dataclass(frozen=True)
class PageDecision:
    page_id: str
    url: str
    action: str  # keep | consolidate_into | retarget | differentiate
    consolidate_target_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    reason_fa: str = ""


@dataclass(frozen=True)
class CannibalizationCluster:
    fingerprint: str
    keyword_sample: str
    decided_by: str
    winner_page_id: str
    pages: tuple[PageDecision, ...]
    reason_codes: tuple[str, ...] = ()
    reason_fa: str = ""


@dataclass(frozen=True)
class CannibalizationResult:
    """نتیجهٔ تشخیص تصادم کیورد اعلام‌شده — نه کانیبالیزیشن کامل بازار."""

    clusters: tuple[CannibalizationCluster, ...]
    skipped_pages: tuple[SkippedPage, ...]


def _normalize_role(role: str) -> str:
    key = (role or "other").strip().lower()
    return key if key in _ROLE_RANK else "other"


def _role_rank(role: str) -> int:
    return _ROLE_RANK[_normalize_role(role)]


def _keyword_tokens(text: str) -> set[str]:
    return set(keyword_content_tokens(text))


def _field_targets_keyword(field: str, keyword: str) -> bool:
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return False
    field_tokens = set(analyze_form(field).split())
    return tokens.issubset(field_tokens)


def _title_h1_score(page: PageTarget) -> int:
    return int(_field_targets_keyword(page.title, page.target_keyword)) + int(
        _field_targets_keyword(page.h1, page.target_keyword)
    )


def _priority_key(page: PageTarget) -> int:
    # Missing priority sorts below any explicit value.
    return page.priority if page.priority is not None else -10**12


def _signal_key(page: PageTarget) -> tuple:
    """معیارهای ۲–۵ (بدون priority) برای تشخیص conflict با override."""
    return (
        _title_h1_score(page),
        _role_rank(page.page_role),
        page.inbound_internal_links,
        page.word_count,
        page.page_id,
    )


def _full_key(page: PageTarget) -> tuple:
    return (_priority_key(page),) + _signal_key(page)


def _pick_winner(pages: list[PageTarget]) -> PageTarget:
    return max(pages, key=_full_key)


def _pick_signal_winner(pages: list[PageTarget]) -> PageTarget:
    return max(pages, key=_signal_key)


def _decided_by(winner: PageTarget, pages: list[PageTarget]) -> str:
    others = [p for p in pages if p.page_id != winner.page_id]
    checks: list[tuple[str, object]] = [
        ("priority", _priority_key(winner)),
        ("title_h1_match", _title_h1_score(winner)),
        ("page_role", _role_rank(winner.page_role)),
        ("internal_links", winner.inbound_internal_links),
        ("word_count", winner.word_count),
        ("page_id_tiebreak", winner.page_id),
    ]
    other_fns = [
        _priority_key,
        _title_h1_score,
        _role_rank_page,
        lambda p: p.inbound_internal_links,
        lambda p: p.word_count,
        lambda p: p.page_id,
    ]
    for (name, wval), fn in zip(checks, other_fns, strict=True):
        if all(wval > fn(o) for o in others):  # type: ignore[operator]
            return name
    return "page_id_tiebreak"


def _role_rank_page(page: PageTarget) -> int:
    return _role_rank(page.page_role)


def _loser_action(
    loser: PageTarget,
    winner: PageTarget,
    *,
    significant_word_count: int,
) -> tuple[str, tuple[str, ...]]:
    """قاعده قطعی اکشن بازنده — ADR-0007.

    مرز: word_count >= significant_word_count → retarget (پس دقیقاً برابر آستانه = retarget).
    word_count < significant_word_count → consolidate_into.
    """
    if _normalize_role(loser.page_role) != _normalize_role(winner.page_role):
        return "differentiate", ("loser_differentiate", "role_differs_from_winner")
    if loser.word_count >= significant_word_count:
        return (
            "retarget",
            (
                "loser_retarget",
                "significant_word_count_threshold",
                f"word_count_gte_{significant_word_count}",
            ),
        )
    return (
        "consolidate_into",
        (
            "loser_consolidate_into",
            "significant_word_count_threshold",
            f"word_count_lt_{significant_word_count}",
        ),
    )


def _action_reason_fa(
    action: str,
    winner: PageTarget,
    loser: PageTarget,
    *,
    significant_word_count: int,
) -> str:
    if action == "differentiate":
        return (
            f"نقش صفحه ({_normalize_role(loser.page_role)}) با برنده "
            f"({_normalize_role(winner.page_role)}) فرق دارد؛ زاویه را جدا کنید، حذف نکنید."
        )
    if action == "retarget":
        return (
            f"نقش یکسان است ولی محتوا قابل توجه است ({loser.word_count} کلمه ≥ "
            f"{significant_word_count})؛ کیورد هدف را عوض کنید."
        )
    return (
        f"نقش یکسان و محتوای کم ({loser.word_count} < {significant_word_count})؛ "
        f"ادغام/۳۰۱ به {winner.page_id} پیشنهاد می‌شود."
    )


def detect_keyword_cannibalization(
    pages: list[PageTarget],
    *,
    significant_word_count: int = SIGNIFICANT_WORD_COUNT,
) -> CannibalizationResult:
    """تصادم کیورد اعلام‌شده را تشخیص می‌دهد و برنده/بازنده‌ها را با اکشن پیشنهاد می‌دهد.

    این کانیبالیزیشن کامل بازار نیست — فقط برخورد target_keywordها پس از fingerprint.

    significant_word_count:
      آستانهٔ «محتوای قابل توجه» برای انتخاب بین retarget و consolidate_into.
      پیش‌فرض ۵۰۰ حدسی است (ASSUMPTION-006)؛ per-site بدون تغییر کد قابل تنظیم است.
      مرز inclusive: word_count >= آستانه → retarget.
    """
    if significant_word_count < 0:
        raise ValueError("significant_word_count must be >= 0")

    skipped: list[SkippedPage] = []
    eligible: list[PageTarget] = []

    for page in pages:
        if not page.target_keyword or not str(page.target_keyword).strip():
            skipped.append(
                SkippedPage(
                    page_id=page.page_id,
                    url=page.url,
                    reason_code="empty_target_keyword",
                    reason_fa="کیورد اعلام‌شده خالی است؛ از تشخیص تصادم حذف شد.",
                )
            )
            continue
        eligible.append(page)

    by_fp: dict[str, list[PageTarget]] = {}
    for page in eligible:
        fp = keyword_fingerprint(page.target_keyword, order_sensitive=False)
        by_fp.setdefault(fp, []).append(page)

    clusters: list[CannibalizationCluster] = []
    for fp, group in sorted(by_fp.items(), key=lambda item: item[0]):
        if len(group) < 2:
            continue

        winner = _pick_winner(group)
        signal_winner = _pick_signal_winner(group)
        decided = _decided_by(winner, group)

        cluster_codes: list[str] = []
        cluster_fa = ""
        if winner.page_id != signal_winner.page_id and winner.priority is not None:
            cluster_codes.append("priority_override_conflicts_signals")
            cluster_fa = (
                f"priority صفحهٔ {winner.page_id} را برنده کرد، در حالی که بر اساس "
                f"سیگنال‌های title/h1، نقش و لینک/حجم، صفحهٔ {signal_winner.page_id} "
                f"برنده می‌شد. اختیار انسان حفظ شد."
            )

        decisions: list[PageDecision] = []
        for page in sorted(group, key=lambda p: p.page_id):
            if page.page_id == winner.page_id:
                decisions.append(
                    PageDecision(
                        page_id=page.page_id,
                        url=page.url,
                        action="keep",
                        reason_codes=(f"winner_by_{decided}",),
                        reason_fa=f"برنده بر اساس معیار {decided}.",
                    )
                )
                continue
            action, codes = _loser_action(
                page, winner, significant_word_count=significant_word_count
            )
            if action not in _ACTIONS:
                raise RuntimeError(f"invalid action {action!r}")
            target = winner.page_id if action == "consolidate_into" else None
            decisions.append(
                PageDecision(
                    page_id=page.page_id,
                    url=page.url,
                    action=action,
                    consolidate_target_id=target,
                    reason_codes=codes,
                    reason_fa=_action_reason_fa(
                        action,
                        winner,
                        page,
                        significant_word_count=significant_word_count,
                    ),
                )
            )

        sample_kw = max(group, key=_full_key).target_keyword
        clusters.append(
            CannibalizationCluster(
                fingerprint=fp,
                keyword_sample=sample_kw,
                decided_by=decided,
                winner_page_id=winner.page_id,
                pages=tuple(decisions),
                reason_codes=tuple(cluster_codes),
                reason_fa=cluster_fa,
            )
        )

    return CannibalizationResult(
        clusters=tuple(clusters),
        skipped_pages=tuple(skipped),
    )
