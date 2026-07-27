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
**برچسب:** `NEEDS-CONFIRMATION` (برش جدا؛ الان دست نزن)
نام ستون `volume` گمراه‌کننده است چون دادهٔ حجم جست‌وجوی فارسی تخمینی است.
ثبت شد برای برش بعدی؛ در این نشست اسکیما عوض نمی‌شود.

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
