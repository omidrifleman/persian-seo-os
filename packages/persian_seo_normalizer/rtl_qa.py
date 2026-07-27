"""QA تایپوگرافی RTL — چیزی که هیچ ابزار سئوی جهانی ندارد."""
from __future__ import annotations

import re
from dataclasses import dataclass

ZWNJ = "\u200c"

_ARABIC_YEH_KAF = re.compile("[\u064a\u0643\u0649]")
_PERSIAN_RANGE = re.compile("[\u0600-\u06ff]")
_MISSING_ZWNJ = re.compile(r"(?<![\w\u0600-\u06ff])(\u0646?\u0645\u06cc) +[\u0600-\u06ff]")
_GLUED_MI = re.compile(r"(?<![\w\u0600-\u06ff])(\u0646?\u0645\u06cc)(?![\u200c ])[\u0600-\u06ff]{2,}")


@dataclass
class RtlFinding:
    code: str
    severity: str  # critical | high | medium | low
    message: str
    sample: str = ""


def audit_rtl_text(text: str, *, field: str = "body") -> list[RtlFinding]:
    """یافته‌های تایپوگرافی/نرمال‌سازی برای تایتل، متا، H1، alt یا بدنه."""
    findings: list[RtlFinding] = []
    is_persian = bool(_PERSIAN_RANGE.search(text))
    critical_fields = {"title", "meta_description", "h1", "slug"}
    sev = "critical" if field in critical_fields else "high"

    m = _ARABIC_YEH_KAF.search(text)
    if m:
        findings.append(RtlFinding(
            "arabic_yeh_kaf", sev,
            "نویسه ی/ك عربی در متن هست؛ گوگل و کلاسترینگ داخلی آن را کلمه دیگری می‌بیند.",
            m.group(0),
        ))

    m = _MISSING_ZWNJ.search(text) or _GLUED_MI.search(text)
    if m:
        findings.append(RtlFinding(
            "zwnj_issue", "medium",
            "نیم‌فاصله پیشوند فعلی نادرست است («می رود» یا «میرود» به‌جای «می‌رود»).",
            m.group(0),
        ))

    if is_persian and re.search(r"[\u06f0-\u06f9]", text) and re.search(r"[0-9]", text):
        findings.append(RtlFinding(
            "mixed_digits", "medium",
            "اعداد فارسی و لاتین در یک فیلد مخلوط شده‌اند؛ ناسازگاری بصری و مشکل تطبیق داده.",
        ))

    if re.search(r"[\u0600-\u06ff][A-Za-z]|[A-Za-z][\u0600-\u06ff]", text):
        findings.append(RtlFinding(
            "bidi_no_space", "low",
            "چسبیدن لاتین به فارسی بدون فاصله باعث شکست نویسه دوجهته در رندر می‌شود.",
        ))

    if is_persian and re.search(r"\s[\u060c\u061f!\.]", text):
        findings.append(RtlFinding(
            "punct_spacing", "low",
            "فاصله قبل از نشانه نگارشی.",
        ))

    if field == "slug" and _PERSIAN_RANGE.search(text) and "%" not in text:
        findings.append(RtlFinding(
            "unencoded_persian_slug", "high",
            "اسلاگ فارسی encode نشده؛ یا percent-encoding کن یا اسلاگ لاتین بگذار.",
        ))

    return findings
