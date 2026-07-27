"""persian-seo-normalizer — لایه نرمال‌سازی فارسی مخصوص سئو.

دو فرم مجزا و هرگز قابل‌جابه‌جایی:
  analyze_form  → برای کلاسترینگ و تطبیق کلیدواژه
  display_form  → برای متن منتشرشدنی
"""

from .normalize import analyze_form, display_form, unify_characters, to_ascii_digits, to_persian_digits
from .fingerprint import keyword_fingerprint, same_keyword, keyword_content_tokens
from .rtl_qa import audit_rtl_text, RtlFinding
from .ezafe import (
    detect_ezafe,
    audit_ezafe_kasreh,
    EzafeMark,
    EzafeBackendUnavailable,
    EzafeCacheError,
    EZAFE_AUDIT_CODE,
)
from .cannibalization import (
    PageTarget,
    PageDecision,
    SkippedPage,
    CannibalizationCluster,
    CannibalizationResult,
    detect_keyword_cannibalization,
    SIGNIFICANT_WORD_COUNT,
)

__all__ = [
    "analyze_form",
    "display_form",
    "unify_characters",
    "to_ascii_digits",
    "to_persian_digits",
    "keyword_fingerprint",
    "same_keyword",
    "keyword_content_tokens",
    "audit_rtl_text",
    "RtlFinding",
    "detect_ezafe",
    "audit_ezafe_kasreh",
    "EzafeMark",
    "EzafeBackendUnavailable",
    "EzafeCacheError",
    "EZAFE_AUDIT_CODE",
    "PageTarget",
    "PageDecision",
    "SkippedPage",
    "CannibalizationCluster",
    "CannibalizationResult",
    "detect_keyword_cannibalization",
    "SIGNIFICANT_WORD_COUNT",
]
__version__ = "0.1.0"
