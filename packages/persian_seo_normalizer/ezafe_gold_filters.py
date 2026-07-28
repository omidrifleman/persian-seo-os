"""Sentence and token quality filters for ezafe gold (no network).

Used by harvest/clean scripts and worksheet/eval/ingest.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .fingerprint import keyword_fingerprint
from .normalize import analyze_form

ZWNJ = "\u200c"

# Relative-time / UI / chrome phrases (substring match after light normalize).
_UI_PHRASES = (
    "ثبت نظر",
    "نمایش بیشتر",
    "همه حقوق",
    "همه‌ حقوق",
    "ورود",
    "ثبت‌نام",
    "ثبت نام",
    "سبد خرید",
    "جستجو",
    "پنل",
    "افزودن به",
    "بازگشت به بالا",
    "نظر شما با موفقیت",
)

_RELATIVE_TIME = re.compile(
    r"(?:\d+|[\d۰-۹٠-٩]+)\s*(?:روز|ساعت|دقیقه|هفته|ماه)\s*(?:قبل|پیش)"
    r"|دیروز|امروز\s+ساعت",
    re.IGNORECASE,
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)

# Conjugated / light-verb endings typical of a real clause (not a nav label).
_FINITE_VERB_END = re.compile(
    r"(?:است|بود|شد|رفت|آمد|کرد|نمود|داشت|هستند|نیست|باشند|باشید"
    r"|می‌\w+|مي\w+|نمى\w+|نمی‌\w+"
    r"|\w+(?:ند|ید|یم|م|ی|د))\s*[.!?؟۔…]?$"
)

_PURE_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)
_PURE_LATIN = re.compile(r"^[A-Za-z]+$")
_PURE_NUMBER = re.compile(r"^[\d۰-۹٠-٩]+$")
_CONTROL_OR_ONLY_ZWNJ = re.compile(r"^[\u0000-\u001f\u007f-\u009f\u200c\u200d\u200e\u200f]+$")

# Closed-class / template glue kept in structural skeleton (rest → "_").
_CLOSED_CLASS = {
    "در",
    "به",
    "از",
    "و",
    "با",
    "را",
    "که",
    "این",
    "آن",
    "یک",
    "یا",
    "تا",
    "بر",
    "برای",
    "است",
    "بود",
    "شد",
    "هست",
    "نیست",
    "روستایی",
    "توابع",
    "بخش",
    "شهرستان",
    "استان",
    "ایران",
    "انگلیسی",
    "زاده",
    "بازیکن",
    "فوتبال",
    "اهل",
    "شهر",
    "دهستان",
    "مرکز",
    "جمعیت",
    "کیلومتر",
    "واقع",
    "واقع‌شده",
    "واقع شده",
}


@dataclass(frozen=True)
class FilterResult:
    ok: bool
    reason: str = ""


def rejection_reason(sentence: str) -> str | None:
    """Return first rejection reason code, or None if sentence passes."""
    s = re.sub(r"\s+", " ", sentence).strip()
    if not s:
        return "empty"
    if "..." in s or "…" in s or "|" in s or "｜" in s:
        return "ellipsis_or_pipe"
    if _EMAIL.search(s) or _URL.search(s):
        return "email_or_url"
    if _RELATIVE_TIME.search(s):
        return "relative_time"
    low = s.replace(ZWNJ, "")
    for phrase in _UI_PHRASES:
        if phrase in low or phrase in s:
            return "ui_chrome"
    tokens = [t for t in re.split(r"\s+", s) if t]
    fa_tokens = [t for t in tokens if re.search(r"[\u0600-\u06FF]", t)]
    if len(fa_tokens) < 7:
        return "too_few_persian_tokens"
    non_fa = 0
    for t in tokens:
        core = t.strip("«»\"'()[]{}،,؛;:.!?؟۔…-_/")
        if not core:
            non_fa += 1
            continue
        if not re.search(r"[\u0600-\u06FF]", core):
            non_fa += 1
    if tokens and (non_fa / len(tokens)) > 0.30:
        return "non_persian_token_ratio"
    # Strip trailing punctuation for verb check.
    end = re.sub(r"[.!?؟۔…»\"']+$", "", s).strip()
    if not _FINITE_VERB_END.search(end):
        return "no_finite_verb_end"
    return None


def passes_body_sentence_filter(sentence: str) -> FilterResult:
    reason = rejection_reason(sentence)
    if reason is None:
        return FilterResult(ok=True)
    return FilterResult(ok=False, reason=reason)


def is_token_labelable(token: str) -> bool:
    """False for pure punct, digits, latin-only, or control/ZWNJ-only tokens."""
    if not token:
        return False
    if _CONTROL_OR_ONLY_ZWNJ.fullmatch(token):
        return False
    if _PURE_PUNCT.fullmatch(token):
        return False
    if _PURE_NUMBER.fullmatch(token):
        return False
    return _PURE_LATIN.fullmatch(token) is None


def sentence_skeleton(text: str) -> str:
    """Mask open-class tokens as '_' using analyze_form; keep closed-class glue."""
    tokens = analyze_form(text).split()
    out: list[str] = []
    for t in tokens:
        if t in _CLOSED_CLASS:
            out.append(t)
        elif re.fullmatch(r"[\d۰-۹٠-٩]+", t):
            out.append("_")
        elif re.fullmatch(r"[^\w\u0600-\u06FF]+", t, flags=re.UNICODE):
            out.append(t)
        else:
            out.append("_")
    return " ".join(out)


def sentence_template_fingerprint(text: str) -> str:
    """Structural fingerprint via existing keyword_fingerprint on skeleton.

    order_sensitive=True so slot positions matter; content names collapse to '_'.
    """
    return keyword_fingerprint(sentence_skeleton(text), order_sensitive=True)


@dataclass(frozen=True)
class TemplateDedupeReport:
    n_in: int
    n_out: int
    n_clusters: int
    largest_cluster: int
    dropped: int


def dedupe_template_clusters(
    texts: Sequence[str],
    *,
    max_per_cluster: int = 3,
) -> tuple[list[int], TemplateDedupeReport]:
    """Keep up to max_per_cluster indices per template fingerprint (stable order).

    Returns (kept_indices, report).
    """
    clusters: dict[str, list[int]] = defaultdict(list)
    for i, text in enumerate(texts):
        fp = sentence_template_fingerprint(text)
        clusters[fp].append(i)
    kept: list[int] = []
    largest = 0
    for idxs in clusters.values():
        largest = max(largest, len(idxs))
        kept.extend(idxs[:max_per_cluster])
    kept.sort()
    report = TemplateDedupeReport(
        n_in=len(texts),
        n_out=len(kept),
        n_clusters=len(clusters),
        largest_cluster=largest,
        dropped=len(texts) - len(kept),
    )
    return kept, report


def filter_sentences_with_report(
    sentences: Iterable[str],
) -> tuple[list[str], list[tuple[str, str]], Counter[str]]:
    """Return (kept, rejected[(text, reason)], reason_counts)."""
    kept: list[str] = []
    rejected: list[tuple[str, str]] = []
    counts: Counter[str] = Counter()
    for s in sentences:
        reason = rejection_reason(s)
        if reason is None:
            kept.append(s)
        else:
            rejected.append((s, reason))
            counts[reason] += 1
    return kept, rejected, counts
