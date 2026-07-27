"""persian-seo-normalizer — لایه نرمال‌سازی فارسی مخصوص سئو.

دو فرم مجزا و هرگز قابل‌جابه‌جایی:
  analyze_form  → برای کلاسترینگ و تطبیق کلیدواژه
  display_form  → برای متن منتشرشدنی
"""

from .cannibalization import (
    SIGNIFICANT_WORD_COUNT,
    CannibalizationCluster,
    CannibalizationResult,
    PageDecision,
    PageTarget,
    SkippedPage,
    detect_keyword_cannibalization,
)
from .ezafe import (
    EZAFE_AUDIT_CODE,
    EzafeBackendUnavailable,
    EzafeCacheError,
    EzafeMark,
    audit_ezafe_kasreh,
    detect_ezafe,
)
from .fingerprint import keyword_content_tokens, keyword_fingerprint, same_keyword
from .normalize import (
    analyze_form,
    display_form,
    to_ascii_digits,
    to_persian_digits,
    unify_characters,
)
from .rtl_qa import RtlFinding, audit_rtl_text

__all__ = [
    "EZAFE_AUDIT_CODE",
    "SIGNIFICANT_WORD_COUNT",
    "CannibalizationCluster",
    "CannibalizationResult",
    "EzafeBackendUnavailable",
    "EzafeCacheError",
    "EzafeMark",
    "PageDecision",
    "PageTarget",
    "RtlFinding",
    "SkippedPage",
    "analyze_form",
    "audit_ezafe_kasreh",
    "audit_rtl_text",
    "detect_ezafe",
    "detect_keyword_cannibalization",
    "display_form",
    "keyword_content_tokens",
    "keyword_fingerprint",
    "same_keyword",
    "to_ascii_digits",
    "to_persian_digits",
    "unify_characters",
]
__version__ = "0.1.0"
