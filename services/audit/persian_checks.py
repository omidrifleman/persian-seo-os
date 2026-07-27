"""چک‌های آدیت اختصاصی فارسی — تمایز فروش ما.

هر چک: id فارسی‌فهم، شدت، توضیح، و «دستور اجرای اصلاح».
این لیست عمداً به‌عنوان داده نگه داشته شده تا هم در گزارش و هم در MCP tool مصرف شود.
"""
from __future__ import annotations

PERSIAN_CHECKS = [
    {
        "id": "fa.title.arabic_chars",
        "severity": "critical",
        "title": "ی/ك عربی در تایتل یا H1",
        "why": "موتور جست‌وجو و کلاسترینگ داخلی، «کيف» و «کیف» را دو کلمه می‌بینند.",
        "fix": "تایتل و H1 را با display_form بازنویسی کن و در CMS ذخیره مجدد بگیر.",
    },
    {
        "id": "fa.title.zwnj",
        "severity": "high",
        "title": "نیم‌فاصله نادرست در تایتل، متا و اسلاگ",
        "why": "«میرود» و «می رود» تطبیق کوئری و خوانایی را خراب می‌کنند.",
        "fix": "اعمال display_form روی تایتل، متا، H1، alt و اسلاگ.",
    },
    {
        "id": "fa.html.lang_dir",
        "severity": "high",
        "title": "نبود یا اشتباه بودن lang=fa و dir=rtl",
        "why": "روی رندر، دسترس‌پذیری و درک زبانی صفحه اثر می‌گذارد.",
        "fix": "در قالب، <html lang=\"fa\" dir=\"rtl\"> ست شود.",
    },
    {
        "id": "fa.url.slug",
        "severity": "high",
        "title": "اسلاگ فارسی encode‌نشده یا ناسازگار",
        "why": "لینک‌سازی، اشتراک‌گذاری و ردیابی را می‌شکند و باعث duplicate می‌شود.",
        "fix": "یک سیاست واحد انتخاب کن: percent-encoding یا اسلاگ لاتین. بعد ریدایرکت ۳۰۱ بزن.",
    },
    {
        "id": "fa.date.jalali_schema_mismatch",
        "severity": "medium",
        "title": "ناسازگاری تاریخ شمسی محتوا با datePublished اسکیما",
        "why": "سیگنال تازگی محتوا را مخدوش می‌کند.",
        "fix": "تاریخ شمسی نمایشی را از منبع میلادی تولید کن، نه دستی.",
    },
    {
        "id": "fa.schema.locale",
        "severity": "medium",
        "title": "اسکیمای فارسی ناقص",
        "why": "inLanguage، نام برند فارسی/لاتین و واحد پول ریال/تومان اغلب غلط ست می‌شوند.",
        "fix": "inLanguage=fa-IR، priceCurrency=IRR، نام برند در دو صورت فارسی و لاتین.",
    },
    {
        "id": "fa.font.rendering",
        "severity": "medium",
        "title": "فونت فارسی ناایمن یا شکست نویسه دوجهته",
        "why": "CLS و خوانایی؛ عدد و برند لاتین وسط جمله فارسی می‌شکند.",
        "fix": "فونت فارسی با font-display: swap و تست بصری تایتل‌های دوجهته.",
    },
    {
        "id": "fa.content.mt_quality",
        "severity": "high",
        "title": "محتوای ترجمه ماشینی بی‌کیفیت",
        "why": "مستقیماً مشمول سیاست scaled content abuse گوگل است.",
        "fix": "صفحه را بازنویسی انسانی کن یا noindex بزن. اولویت بالا.",
    },
    {
        "id": "fa.digits.mixed",
        "severity": "low",
        "title": "اعداد فارسی و لاتین مخلوط",
        "why": "ناسازگاری بصری و مشکل در تطبیق داده و قیمت.",
        "fix": "یک سیاست عددی برای کل سایت و اعمال آن در لایه قالب.",
    },
    {
        "id": "fa.text.missing_ezafe_kasreh",
        "severity": "low",
        "title": "کسره اضافه تشخیص‌داده‌شده ولی نانوشته در متن",
        "why": "کسره اضافه معنای عبارت کلیدی را عوض می‌کند و معمولاً در خط نوشته نمی‌شود.",
        "fix": "در مسیر آدیت با audit_ezafe_kasreh بازبینی کن؛ به display_form وصل نکن.",
    },
]


def by_severity(severity: str) -> list[dict]:
    return [c for c in PERSIAN_CHECKS if c["severity"] == severity]
