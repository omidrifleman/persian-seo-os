# ADR-0007 — تشخیص تصادم کیورد اعلام‌شده (keyword cannibalization)

**وضعیت:** پذیرفته‌شده

## محدودیت محصول (الزامی)
این تابع فقط **تصادم کیورد اعلام‌شده** را تشخیص می‌دهد: صفحاتی که
`target_keyword` آن‌ها پس از `keyword_fingerprint` یکی است.
کانیبالیزیشن واقعی — دو صفحه سر کیوردی که هیچ‌کدام اعلام نکرده‌اند —
فقط با دادهٔ GSC قابل تشخیص است و برش جداست. در مستندات محصول ادعای
پوشش کامل نشود.

## تصمیم: معیار برنده (lexicographic)
1. `priority` صریح (انسان/سیستم) — بالاتر برنده
2. تطبیق title+h1 با کیورد (۰..۲)
3. `page_role`: pillar > commercial > informational > other
4. `inbound_internal_links` سپس `word_count`
5. `page_id` lexicographic برای قطعیت

`decided_by` نام اولین معیاری است که برنده را از بقیه جدا کرد.
اگر `page_id_tiebreak` باشد توصیه ضعیف است.

### شفافیت override با priority
اگر برنده‌ای که فقط با معیارهای ۲–۴ انتخاب می‌شود ≠ برنده‌ای که با priority
انتخاب می‌شود، کلاستر `reason_codes` شامل
`priority_override_conflicts_signals` می‌گیرد و در `reason_fa` می‌گوید
کدام صفحه بر اساس سیگنال‌ها برنده بود. اختیار انسان حفظ می‌شود ولی بی‌صدا نیست.

## اکشن بازنده‌ها (قطعی — بدون noindex در این برش)
- نقش ≠ برنده → `differentiate`
- نقش یکسان و `word_count >= significant_word_count` → `retarget`
  (مرز inclusive: دقیقاً برابر آستانه = retarget)
- نقش یکسان و `word_count < significant_word_count` → `consolidate_into`

`significant_word_count` پارامتر تابع است (پیش‌فرض ۵۰۰؛ ASSUMPTION-006).
وقتی این آستانه اکشن را عوض می‌کند، `reason_codes` شامل
`significant_word_count_threshold` است.

`noindex` در enum نیست تا قاعدهٔ تولید نداشته باشد.

## کیورد خالی
صفحه از کلاستربندی حذف و در `skipped_pages` با دلیل گزارش می‌شود.
