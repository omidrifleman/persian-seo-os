"""persian-seo-normalizer — لایه نرمال‌سازی فارسی مخصوص سئو.

دو فرم مجزا و هرگز قابل‌جابه‌جایی:
  analyze_form  → برای کلاسترینگ و تطبیق کلیدواژه
  display_form  → برای متن منتشرشدنی
"""

from .normalize import analyze_form, display_form, unify_characters, to_ascii_digits, to_persian_digits
from .fingerprint import keyword_fingerprint, same_keyword
from .rtl_qa import audit_rtl_text, RtlFinding
from .ezafe import detect_ezafe, EzafeMark, EzafeBackendUnavailable

__all__ = [
    "analyze_form",
    "display_form",
    "unify_characters",
    "to_ascii_digits",
    "to_persian_digits",
    "keyword_fingerprint",
    "same_keyword",
    "audit_rtl_text",
    "RtlFinding",
    "detect_ezafe",
    "EzafeMark",
    "EzafeBackendUnavailable",
]
__version__ = "0.1.0"
