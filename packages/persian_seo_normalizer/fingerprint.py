"""تشخیص اینکه دو کوئری فارسی در واقع یک کلیدواژه‌اند."""
from __future__ import annotations

import hashlib

from .normalize import analyze_form

# استاپ‌وردهایی که در سئو معنای intent را عوض نمی‌کنند
_SEO_STOPWORDS = {
    "\u062f\u0631",      # در
    "\u0628\u0647",      # به
    "\u0627\u0632",      # از
    "\u0648",            # و
    "\u0628\u0627",      # با
    "\u0631\u0627",      # را
    "\u0628\u0631\u0627\u06cc",  # برای
}


def keyword_content_tokens(text: str) -> list[str]:
    """توکن‌های معنایی کیورد پس از analyze_form و حذف استاپ‌وردهای سئو."""
    return [t for t in analyze_form(text).split() if t not in _SEO_STOPWORDS]


def keyword_fingerprint(text: str, *, order_sensitive: bool = False) -> str:
    """اثر انگشت کلیدواژه.

    order_sensitive=False یعنی «قیمت لپ تاپ» و «لپ تاپ قیمت» یک اثر انگشت دارند.
    برای intentهای ناوبری/برند بهتر است True بگذاری.
    """
    tokens = keyword_content_tokens(text)
    if not order_sensitive:
        tokens = sorted(tokens)
    joined = " ".join(tokens)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def same_keyword(a: str, b: str, *, order_sensitive: bool = False) -> bool:
    return keyword_fingerprint(a, order_sensitive=order_sensitive) == keyword_fingerprint(
        b, order_sensitive=order_sensitive
    )
