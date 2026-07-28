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
from .keyword_cluster import (
    ClusterResult,
    KeywordCluster,
    KeywordInput,
    KeywordRecord,
    SkippedKeyword,
    cluster_keywords,
    detect_search_intent,
    make_cluster_id,
)
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
    "ClusterResult",
    "EzafeBackendUnavailable",
    "EzafeCacheError",
    "EzafeMark",
    "KeywordCluster",
    "KeywordInput",
    "KeywordRecord",
    "PageDecision",
    "PageTarget",
    "RtlFinding",
    "SkippedKeyword",
    "SkippedPage",
    "analyze_form",
    "audit_ezafe_kasreh",
    "audit_rtl_text",
    "cluster_keywords",
    "detect_ezafe",
    "detect_keyword_cannibalization",
    "detect_search_intent",
    "display_form",
    "keyword_content_tokens",
    "keyword_fingerprint",
    "make_cluster_id",
    "same_keyword",
    "to_ascii_digits",
    "to_persian_digits",
    "unify_characters",
]
__version__ = "0.1.0"
