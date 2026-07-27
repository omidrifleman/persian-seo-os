"""نرمال‌سازی متن فارسی برای سئو.

قاعده طلایی: analyze_form را هرگز منتشر نکن، display_form را هرگز برای مقایسه استفاده نکن.
"""
from __future__ import annotations

import re
import unicodedata

ZWNJ = "\u200c"
ZWJ = "\u200d"

# ی/ك عربی و گونه‌های همزه
_CHAR_MAP = {
    "\u064a": "\u06cc",  # ARABIC YEH -> FARSI YEH
    "\u0649": "\u06cc",  # ALEF MAKSURA
    "\u0643": "\u06a9",  # ARABIC KAF -> KEHEH
    "\u06aa": "\u06a9",
    "\u0629": "\u0647",  # TEH MARBUTA -> HEH
    "\u0624": "\u0648",
    "\u0625": "\u0627",
    "\u0623": "\u0627",
    "\u0622": "\u0622",
    "\u0671": "\u0627",
}

# اعراب، تنوین، کشیده
_DIACRITICS = re.compile("[\u064b-\u065f\u0670\u0640\u06d6-\u06ed]")

_PERSIAN_DIGITS = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
_ARABIC_DIGITS = "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
_ASCII_DIGITS = "0123456789"

_TO_ASCII = {ord(c): _ASCII_DIGITS[i] for i, c in enumerate(_PERSIAN_DIGITS)}
_TO_ASCII.update({ord(c): _ASCII_DIGITS[i] for i, c in enumerate(_ARABIC_DIGITS)})
_TO_PERSIAN = {ord(c): _PERSIAN_DIGITS[i] for i, c in enumerate(_ASCII_DIGITS)}
_TO_PERSIAN.update({ord(c): _PERSIAN_DIGITS[i] for i, c in enumerate(_ARABIC_DIGITS)})

# پیشوندهای فعلی که نیم‌فاصله می‌گیرند
_VERB_PREFIXES = ("\u0645\u06cc", "\u0646\u0645\u06cc")  # می، نمی
# پسوندهای رایج که نیم‌فاصله می‌گیرند
_SUFFIXES = (
    "\u0647\u0627\u06cc\u06cc", "\u0647\u0627\u06cc", "\u0647\u0627",   # هایی، های، ها
    "\u062a\u0631\u06cc\u0646", "\u062a\u0631",                       # ترین، تر
)

_PERSIAN_PUNCT = {",": "\u060c", ";": "\u061b", "?": "\u061f"}


def unify_characters(text: str) -> str:
    """یکسان‌سازی نویسه‌های عربی/فارسی و حذف اعراب. پایه هر دو فرم."""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(str.maketrans(_CHAR_MAP))
    text = _DIACRITICS.sub("", text)
    return text.replace(ZWJ, "")


def to_ascii_digits(text: str) -> str:
    return text.translate(_TO_ASCII)


def to_persian_digits(text: str) -> str:
    return text.translate(_TO_PERSIAN)


def analyze_form(text: str) -> str:
    """فرم canonical برای کلاسترینگ، تطبیق و کلید یکتای دیتابیس.

    - ی/ك عربی یکسان می‌شود
    - اعراب و کشیده حذف می‌شود
    - اعداد به ASCII می‌روند
    - ZWNJ حذف می‌شود («می‌رود» == «میرود» == «می رود»)
    - فاصله‌ها فشرده و لاتین lowercase می‌شود
    """
    text = unify_characters(text)
    text = to_ascii_digits(text)
    text = text.replace(ZWNJ, "")
    # «می رود» با فاصله معمولی هم باید به «میرود» برسد
    for pref in _VERB_PREFIXES:
        text = re.sub(rf"(?<![\w\u0600-\u06ff]){pref} +(?=[\u0600-\u06ff])", pref, text)
    for suf in _SUFFIXES:
        text = re.sub(rf"(?<=[\u0600-\u06ff]) +{suf}(?![\w\u0600-\u06ff])", suf, text)
    text = re.sub(r"[\u060c\u061b\u061f!\.\,\;\?\:\"'\(\)\[\]\u00ab\u00bb]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def display_form(text: str) -> str:
    """متن قابل انتشار: نیم‌فاصله صحیح، اعداد فارسی، فاصله‌گذاری درست نگارشی."""
    text = unify_characters(text)
    text = re.sub(r"[ \t]+", " ", text)

    # نیم‌فاصله پیشوند فعلی: «می رود» و «میرود» → «می‌رود»
    for pref in _VERB_PREFIXES:
        text = re.sub(rf"(?<![\w\u0600-\u06ff]){pref}[ {ZWNJ}]*(?=[\u0600-\u06ff])", pref + ZWNJ, text)

    # نیم‌فاصله پسوند
    for suf in _SUFFIXES:
        text = re.sub(rf"(?<=[\u0600-\u06ff])[ {ZWNJ}]*{suf}(?![\w\u0600-\u06ff])", ZWNJ + suf, text)

    # نشانه‌های نگارشی لاتین → فارسی، فقط وقتی متن فارسی است
    if re.search(r"[\u0600-\u06ff]", text):
        for latin, persian in _PERSIAN_PUNCT.items():
            text = text.replace(latin, persian)

    # فاصله بعد از نشانه، نه قبل از آن
    text = re.sub(r"\s+([\u060c\u061b\u061f!\.\:])", r"\1", text)
    text = re.sub(r"([\u060c\u061b\u061f!\.\:])(?=[^\s\d])", r"\1 ", text)

    text = to_persian_digits(text)
    return re.sub(r"\s+", " ", text).strip()
