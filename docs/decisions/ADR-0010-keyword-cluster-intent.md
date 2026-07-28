# ADR-0010 — خوشه‌بندی کلیدواژه با هستهٔ موضوع + نیت واژگانی

**وضعیت:** پذیرفته‌شده

## زمینه
خوشه‌بندی فقط با `keyword_fingerprint` روی کل عبارت عملاً حذف تکراری است:
روی فهرست واقعی تقریباً همه خوشه‌ها تک‌عضوی می‌شوند و مسئلهٔ «یک موضوع،
چند زاویهٔ نیت» حل نمی‌شود.

## تصمیم: کلید دو بخشی
```
cluster_id = f"{topic_core_fingerprint}:{intent}"
topic_core_fingerprint = keyword_fingerprint(" ".join(topic_core_tokens))
```
`topic_core_tokens` = توکن‌های محتوا (`keyword_content_tokens`) منهای توکن‌های
نشانگرهای **strippable** آتش‌گرفته. منطق اثرانگشت موازی نوشته نمی‌شود.

اگر پس از حذف نشانگرهای strippable توکنی نماند → skip با `only_intent_markers`.

`order_sensitive=False` پیش‌فرض است (همان قرارداد fingerprint برای سئو).

## نشانگر نیت

### مصرف موقعیت (همپوشانی)
پویش چپ‌به‌راست: در هر موقعیت، طولانی‌ترین نشانگر منطبق انتخاب می‌شود و
بازهٔ توکن مصرف می‌شود تا نشانگر کوتاه‌تر روی همان بازه دوباره نزند.
مثال: «قیمت خرید لپ تاپ» → فقط «قیمت خرید» (نه «قیمت»+«خرید»).

### strippable در برابر موضوع‌مان
یک فهرست دو نقش ندارد:
- `strippable=True`: تعدیل‌گر نیت (خرید، قیمت، بهترین، چیست، ورود، …)
  — از هسته حذف
- `strippable=False`: اسم‌هایی که خود موضوع‌اند (فروشگاه، نمایندگی، بررسی،
  نمونه، …) — نیت می‌سازند ولی در `topic_core` می‌مانند

`FiredIntentMarker` (surface + intent + strippable) روی رکورد ذخیره می‌شود؛
lookup شکنندهٔ سطح→strippable با پیش‌فرض بی‌صدا ممنوع است.

### navigational — فقط الگوی واقعی ناوبری
اسم عام «سایت» / «اپ» / «تلگرام» نشانگر مستقل نیست («طراحی سایت» خدماتی است،
نه ناوبری → `unknown` با هستهٔ `{طراحی، سایت}`).

الگوهای نگه/افزوده‌شده (همگی strippable): `ورود`، `لاگین`، `سایت رسمی`،
`ورود به سایت`، `پنل کاربری`.
مثال: «سایت رسمی ایرانسل» → navigational، هسته `{ایرانسل}`.

«بررسی» در informational است (محتوای تحلیلی فارسی)، نه commercial.

نسخهٔ یک: فقط نشانگر واژگانی ثابت در کد. بدون LLM، بدون برند لاتین تک‌توکن.

### کاتالوگ: ادغام فقط برای هم‌ارز کامل
دو surface با توکن analyze یکسان فقط اگر intent و strippable یکی باشند ادغام
می‌شوند؛ در غیر این صورت `ValueError` (افت بی‌صدا ممنوع).

### تعارض نشانگر — اولویت ثابت
`transactional > commercial > informational > navigational`.

دلیل محصولی: عبارت‌هایی مثل «خرید بهترین لپ تاپ ارزان» رایج و پرارزش‌اند؛
`unknown` کردنشان ابزار را روی بهترین کوئری‌ها بی‌فایده می‌کند.

الزام شفافیت: همهٔ دسته‌های آتش‌گرفته در `intent_reason_codes`، کد
`multiple_intent_categories`، و فیلد `competing_intent_categories`.

### چرا این با انجماد کسره (ASSUMPTION-008 / ADR-0009) فرق دارد؟
کسره یک علامت اختیاری املایی است؛ نبودش خطای سئویی قطعی نیست و هزینهٔ
برچسب طلایی توجیه نداشت → FROZEN.
اینجا قاعدهٔ زبانی-تجاری مستند داریم و خروجی همراه reason code است.

## انتخاب head
یک تابع رتبه (`_rank_members`) فهرست کامل را برمی‌گرداند؛ head = عضو اول،
`head_decided_by` از مقایسهٔ عضو اول و دوم همان فهرست — تا با دو حلقهٔ جدا
ناسازگار نشود.

1. `search_demand_status` (known > estimated > unknown)
2. `search_demand` وقتی status ≠ unknown — **صفر با `known` معتبر است**
3. کوتاه‌تر بودن توکن‌های محتوا
4. کوتاه‌تر بودن سطح متن
5. `keyword_id` lexicographic

### محدودیت صریح
در نبود دادهٔ حجم (`unknown` برای همه)، معیارهای ۱–۲ بی‌اثر می‌شوند و
عملاً **طول** (و در نهایت `keyword_id`) head را تعیین می‌کند.

### reason_codes خوشه
کدهای سطح‌عضو از **اجتماع** همهٔ اعضا (ترتیب: head سپس بقیه بر
`keyword_id`)؛ `singleton_cluster` سطح‌خوشه جداست.

`skipped` بر `(keyword_id, reason_code, text)` مرتب است.

### کدهای skip حجم (تفکیک‌شده)
- `invalid_demand_status` — مقدار status خارج از known/estimated/unknown
- `missing_search_demand` — status معتبر ولی عدد نیست
- `negative_search_demand` — عدد منفی
- `demand_status_conflict` — unknown همراه عدد

## خارج از دامنه
`cluster_to_page_targets` ساخته نمی‌شود.
ابزار MCP `keywords.volume_lookup` حذف شده (ASSUMPTION-004).
