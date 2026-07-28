# فرض‌های باز / بسته‌شده

---

## ASSUMPTION-001 — شکل خروجی `detect_ezafe`
**برچسب:** `CONFIRMED`
**فرض:** تابع عمومی لیست span/مارک برمی‌گرداند (`list[EzafeMark]`) و متن را mutate نمی‌کند؛ اتصال به `display_form` در برش بعدی است.
`EzafeMark` فیلد `confidence` در بازهٔ ۰..۱ دارد.

## ASSUMPTION-002 — تصمیم‌های بیزنسی CMS / مدل ارائه / کلید API
**برچسب:** `CONFIRMED`
CMS=وردپرس فقط (ADR-0004)، ارائه=سرویس محصول‌سازی‌شده (ADR-0005)،
کلید=پلتفرم+سهمیه per-tenant و BYOK اختیاری (ADR-0006). RLS معوق (ADR-0003).

## ASSUMPTION-003 — API داخلی DadmaTools برای kasreh
**برچسب:** `CONFIRMED`
**یافته:** `token._.kasreh` با برچسب رشته‌ای (مثلاً `S-kasreh` / `O`).
هر غیر-`O` مثبت است؛ برچسب خام در `raw_label`؛ `confidence=None` چون امتیاز نیست
(None را ۱.۰ نخوان). اتصال به `display_form` هنوز ممنوع.

## ASSUMPTION-004 — volume vs تخمین حجم
**برچسب:** `NEEDS-CONFIRMATION` (برش خوشه‌بندی کلیدواژه باید نام را اصلاح کند)
نام ابزار/ستون‌های شبیه `volume` / `volume_lookup` گمراه‌کننده است چون دادهٔ
حجم جست‌وجوی فارسی اغلب تخمینی یا ناموجود است. هر فیلد حجم باید سه حالت
صریح داشته باشد: `known` / `estimated` / `unknown` — هرگز عدد ساختگی.
پیشنهاد نام: `search_demand` + `search_demand_status` (نه `volume_lookup`).

## ASSUMPTION-005 — skipped در گِیت کیفیت هرگز pass نیست
**برچسب:** `CONFIRMED` (قرارداد؛ مصرف‌کننده هنوز نوشته نشده)
نتیجهٔ چک آدیت ezafe سه‌حالتی است: pass / ایراد (`skipped=False`) /
نامعلوم (`skipped=True` + `skip_reason`). یافتهٔ skipped نباید در quality gate
سبز شود. جزئیات: docstringهای `RtlFinding` و `audit_ezafe_kasreh` و ADR-0002.

## ASSUMPTION-006 — آستانهٔ significant_word_count=500 حدسی است
**برچسب:** `NEEDS-CONFIRMATION`
پیش‌فرض `significant_word_count=500` در `detect_keyword_cannibalization` از دادهٔ
فارسی یا بنچمارک سایت نیامده؛ حدس مهندسی است و برای صفحهٔ محصول (اغلب کوتاه‌تر)
احتمالاً نامناسب است. پارامتر تابع است تا per-site عوض شود.
**شرط بسته‌شدن:** یا با نمونهٔ واقعی مشتری (توزیع word_count صفحات هم‌نقش) کالیبره
شود، یا آستانهٔ per-`page_role` در ADR جدا تعریف و با تست تأیید شود.

## ASSUMPTION-007 — غیرقطعی بودن kasreh در DadmaTools 2.3.6
**برچسب:** `CONFIRMED` (علت مشخص شد؛ mitigation با shim — ADR-0009)
در «کتاب علی» با کش گرم، نرخ شکست حدود ۱ از ۱۰ در اجرای کل سوئیت مشاهده شد.
رفتار درون‌پروسه‌ای قطعی است (۲۰۰/۲۰۰). علت: آداپتور `embedding` با وزن تصادفی
ساخته می‌شود و مسیر `_load_adapter_weights` برای kasreh یا زودبازمى‌گردد
(`model_name='ner'` ∉ pipelines) یا needleی `adapters.kasreh.adapter` با کلیدهای
`layer_text_task_adapters.ner.*` جفت نمی‌شود — صفر کلید کپی می‌شود.
فرضیهٔ نشت سینگلتون بین تست‌ها رد شد (حالت ezafe-only هم ~۲۰٪ می‌شکست).
**شرط بسته‌شدن:** shim در لایهٔ خودمان کلیدها را منتقل کند (تست واحد: انتقال ۰ → قرمز)
و سنجش seed ۰..۴ روی ۲۵ پروسه خروجی یکسان درست بدهد؛ حذف نهایی با رفع بالادستی.

## ASSUMPTION-008 — نام تسک `ner` داخل `*.kasreh.mdl`
**برچسب:** `FROZEN`
آداپتورهای داخل `persian.kasreh.mdl` با نام تسک `ner`
(`layer_text_task_adapters.ner.*`) ذخیره شده‌اند. فرض کاری shim این است که
این همان آداپتور آموزش‌دیدهٔ کسره است که نامش از اسکلت/اسکریپت NER به ارث
رسیده، نه وزن‌های فایل `persian.ner.mdl`.

### شاهد مقایسه مستقیم (کش محلی، ۲۰۲۶-۰۷-۲۸)
فایل‌ها: `persian.kasreh.mdl` vs `persian.ner.mdl` (HuggingFace Dadmatech).
- مجموعه کلیدهای `adapters`: **یکسان** — N_COMMON=53، ONLY_KASREH=0، ONLY_NER=0
- قابل‌مقایسه (shape یکسان): 50 کلید — **BIT_EQUAL=0** (هیچ‌کدام بیت‌به‌بیت یکسان نیست)
- shape mismatch: 3 کلید هد/CRF (`crit._transitions` 2×2 vs 29×29؛
  `entity_label_ffn.layers.1.*` 2 vs 29 کلاس)
- بیشترین اختلاف مطلق روی کلیدهای هم‌شکل:
  `max_abs_diff=0.8082236051559448` روی `entity_label_ffn.layers.0.weight`
- روی خود آداپتورهای XLM-R نیز همه `torch.equal=False`؛ مثلاً
  `layer.11...adapter_up.weight` max_abs≈0.3814

**تفسیر:** فایل کسره همان کپی بایت‌به‌بایت NER نیست؛ وزن‌ها متفاوت‌اند.
نام تسک `ner` احتمالاً ارث اسکلت آموزش است. این شاهد قوی برای ادامهٔ shim است،
نه اثبات کیفیت برچسب روی دادهٔ واقعی.

### انجماد (۲۰۲۶-۰۷-۲۸)
برش اعتبارسنجی F1 انسانی متوقف و فرض **FROZEN** شد.
**دلیل:** ارزش سئویی چک مشتری‌رو `fa.text.missing_ezafe_kasreh` پایین است —
علامت کسره در نوشتار فارسی اختیاری است و نبودش خطای املایی نیست؛ هزینهٔ
برچسب‌گذاری طلایی و آستانهٔ پذیرش توجیه ندارد.
`EZAFE_CUSTOMER_AUDIT_ENABLED=False` می‌ماند. shim قطعیت، تست‌ها و کد مسیر
آدیت (با `force=True` در واحد) سر جایشان‌اند. ازسرگیری فقط با تصمیم محصولی
صریح و بودجهٔ برچسب انسانی (نه به‌صورت پیش‌فرض در برش بعدی).
