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
- `strippable=True`: تعدیل‌گر نیت (خرید، قیمت، بهترین، چیست، …) — از هسته حذف
- `strippable=False`: اسم‌هایی که خود موضوع‌اند (سایت، فروشگاه، اپلیکیشن،
  بررسی، …) — نیت می‌سازند ولی در `topic_core` می‌مانند

بدون این تفکیک، «طراحی سایت» و «طراحی اپلیکیشن» هم‌خوشه می‌شدند.

«بررسی» در informational است (محتوای تحلیلی فارسی)، نه commercial.

نسخهٔ یک: فقط نشانگر واژگانی ثابت در کد. بدون LLM، بدون برند لاتین تک‌توکن
(`laptop` / `gaming` → `unknown`).

### تعارض نشانگر — اولویت ثابت
`transactional > commercial > informational > navigational`.

دلیل محصولی: عبارت‌هایی مثل «خرید بهترین لپ تاپ ارزان» رایج و پرارزش‌اند؛
`unknown` کردنشان ابزار را روی بهترین کوئری‌ها بی‌فایده می‌کند.

الزام شفافیت: همهٔ دسته‌های آتش‌گرفته در `intent_reason_codes`، کد
`multiple_intent_categories`، و فیلد `competing_intent_categories`.

### چرا این با انجماد کسره (ASSUMPTION-008 / ADR-0009) فرق دارد؟
کسره یک علامت اختیاری املایی است؛ نبودش خطای سئویی قطعی نیست و هزینهٔ
برچسب طلایی توجیه نداشت → FROZEN.
اینجا قاعدهٔ زبانی-تجاری مستند داریم (اولویت نیت خرید بر مقایسه) و خروجی
همراه reason code است؛ «حدس پنهان» نیست.

## انتخاب head
1. `search_demand_status` (known > estimated > unknown)
2. `search_demand` وقتی status ≠ unknown — **صفر با `known` معتبر است**
3. کوتاه‌تر بودن توکن‌های محتوا
4. کوتاه‌تر بودن سطح متن
5. `keyword_id` lexicographic

معیار «نیت شناخته‌شده» حذف شد چون نیت جزو کلید خوشه است.

### محدودیت صریح
در نبود دادهٔ حجم (`unknown` برای همه)، معیارهای ۱–۲ بی‌اثر می‌شوند و
عملاً **طول** (و در نهایت `keyword_id`) head را تعیین می‌کند.

### reason_codes خوشه
کدهای سطح‌عضو (`intent_*`, `multiple_intent_categories`, …) از **اجتماع**
همهٔ اعضا (ترتیب: head سپس بقیه بر `keyword_id`) ساخته می‌شوند، نه فقط از
head — تا تعارض نیت در عضو غیر-head گم نشود. پرچم سطح‌خوشه
`singleton_cluster` جدا اضافه می‌شود.

`skipped` در خروجی بر `(keyword_id, reason_code, text)` مرتب است تا ترتیب
لیست به جایگشت ورودی وابسته نباشد. (تکرار `keyword_id` با متن متفاوت هنوز
«اولین در ورودی» را نگه می‌دارد و ذاتاً به ترتیب وابسته است.)

### کدهای skip حجم (تفکیک‌شده)
- `invalid_demand_status` — مقدار status خارج از known/estimated/unknown
- `missing_search_demand` — status معتبر ولی عدد نیست
- `negative_search_demand` — عدد منفی
- `demand_status_conflict` — unknown همراه عدد

## خارج از دامنه
`cluster_to_page_targets` ساخته نمی‌شود. کلیدواژه صفحه نیست؛ تغذیهٔ جعلی
اعضای خوشه به `detect_keyword_cannibalization` توتولوژی است.

ابزار MCP `keywords.volume_lookup` از فهرست TOOLS حذف شده است
(ASSUMPTION-004). فیلدهای ورودی: `search_demand` / `search_demand_status`.
