# Plan 001 — تشخیص ezafe در persian_seo_normalizer

**ایست ۱ — منتظر تأیید قبل از کد**

## استدلال دوفرمی
- `analyze_form` از قبل اعراب (`U+064B`–`U+065F` شامل کسره) را حذف می‌کند؛ وابستگی fingerprint به ezafe غلط و شکننده است.
- تشخیص ezafe فرادادهٔ ساختاری است برای فهم عبارت و (بعداً) غنی‌سازی نمایش؛ متعلق به دامنهٔ نزدیک به `display_form` / QA است، نه کلید تطبیق.
- بنابراین: تابع جدا (`detect_ezafe`)، بدون تغییر معنای `analyze_form` / `keyword_fingerprint` در این برش.
- اگر روزی کسرهٔ دیدنی به متن نمایش تزریق شد، فقط از مسیر `display_form` یا تابع نمایشی جدا — و با تست idempotency.

## نام تابع عمومی
`detect_ezafe(text: str) -> list[EzafeMark]`

همراه با:
- `EzafeMark` (dataclass: `index`, `token`, `has_ezafe`, `confidence` در ۰..۱)
- `EzafeBackendUnavailable` (خطای روشن وقتی backend نیست)
- Protocol داخلی `_EzafeBackend` + پیاده‌سازی `DadmaEzafeBackend`
- **import تنبل:** `dadmatools` فقط داخل متد backend؛ import سطح ماژول `ezafe.py` ممنوع
- بدون نصب dadmatools: فراخوانی `detect_ezafe` → `EzafeBackendUnavailable` با پیام که extras `nlp` را اشاره کند

الگوی موجود: مثل `audit_rtl_text` + `RtlFinding` — تشخیص‌محور، dataclass، export از `__init__`.

## تغییرات فایل‌به‌فایل

| فایل | تغییر |
| --- | --- |
| `packages/persian_seo_normalizer/ezafe.py` | **جدید** — `EzafeMark` (+confidence)، خطا، Protocol، Dadma با lazy import، `detect_ezafe` |
| `packages/persian_seo_normalizer/__init__.py` | export `detect_ezafe`, `EzafeMark`, `EzafeBackendUnavailable` |
| `packages/persian_seo_normalizer/tests/test_ezafe.py` | **جدید** — شامل تست import پایه بدون nlp |
| `docs/decisions/ADR-0002-dadmatools-ezafe-backend.md` | ثبت لایسنس/URL/تاریخ کامیت (نوشته شده) |
| `pyproject.toml` | `nlp = ["dadmatools==2.3.6", "hazm"]` — نسخه دقیق پین |

عمداً تغییر نمی‌دهیم: `normalize.py`, `fingerprint.py`, اسکیما، MCP، gateway.

## فهرست تست‌ها (`test_ezafe.py`)
1. `test_base_package_import_without_nlp_extras` — import پکیج پایه بدون dadmatools/torch
2. `test_missing_backend_raises_clear_error` — بدون backend → `EzafeBackendUnavailable` + اشاره به extras
3. `test_detect_ezafe_returns_marks_with_mock_backend` — mock → `EzafeMark` با confidence ∈ [0,1]
4. `test_empty_and_whitespace` — `""` و فقط فاصله → لیست خالی
5. `test_emoji_and_mixed_script_do_not_crash` — فارسی + لاتین + ایموجی با mock
6. `test_public_exports` — import از ریشهٔ پکیج
7. `test_mark_list_idempotent_re_detect` — دو بار detect → نتیجه یکسان
8. `test_confidence_required_on_marks` — هر mark فیلد confidence عددی ۰..۱ دارد

۳۶ تست موجود نباید بشکند.

## Definition of Done
- [ ] `detect_ezafe` و انواع مرتبط export شده‌اند
- [ ] بدون `nlp` extras: خطای روشن، تست سبز
- [ ] با mock backend: تشخیص ساخت‌یافته، تست سبز
- [ ] `python -m unittest discover -s packages -p "test_*.py" -v` — همه سبز (۳۶ + تست‌های جدید)
- [ ] ponytail سطح `full` روی diff (بدون حذف ایمنی دوفرمی)
- [ ] code-review خودی و رفع ایراد
- [ ] گزارش ایست ۲ بدون کامیت خودسرانه

## ترتیب اجرا پس از تأیید
1. `/speckit.tasks` → تکیت‌های tracer-bullet
2. TDD: اول تست، بعد کد
3. unittest کامل
4. ponytail full
5. code-review
