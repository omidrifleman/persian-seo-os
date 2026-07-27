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
**برچسب:** `NEEDS-CONFIRMATION` (رفتار runtime؛ تست‌ها با mock پوشش می‌دهند)
**فرض:** backend از pipeline `tok,kasreh` با import تنبل داخل متد استفاده می‌کند؛
نسخه پین‌شده `dadmatools==2.3.6`. اگر شکل API فرق کند فقط adapter عوض می‌شود.

## ASSUMPTION-004 — volume vs تخمین حجم
**برچسب:** `NEEDS-CONFIRMATION` (برش جدا؛ الان دست نزن)
نام ستون `volume` گمراه‌کننده است چون دادهٔ حجم جست‌وجوی فارسی تخمینی است.
ثبت شد برای برش بعدی؛ در این نشست اسکیما عوض نمی‌شود.
