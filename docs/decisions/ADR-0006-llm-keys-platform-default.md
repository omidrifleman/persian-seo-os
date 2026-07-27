# ADR-0006 — کلید LLM: کلید خودمان + سهمیه per-tenant؛ BYOK اختیاری

**وضعیت:** پذیرفته‌شده (اسکیما مستند شد؛ پیاده‌سازی کد موکول)

## زمینه
BYOK اجباری با مدل ارائهٔ سرویس محصول‌سازی‌شده (ADR-0005) در تناقض است:
کلید عملاً دست ماست. مهم‌تر: مشتری ایرانی معمولاً نمی‌تواند کلید OpenAI/Anthropic
بگیرد — BYOK اجباری یعنی بازار هدف صفر.

## تصمیم
1. **پیش‌فرض:** کلید متعلق به ما + سهمیه ماهانه per-tenant.
2. **BudgetGuard per-tenant اجباری** است، نه فقط سقف سراسری.
3. هزینه در قیمت‌گذاری منتقل می‌شود، نه جذب یارانه‌ای.
4. **BYOK مسیر اختیاری** برای مشتری بزرگ؛ `llm_gateway` باید هر دو حالت را بپذیرد.

## تغییر اسکیما (پیاده‌سازی در مایگریشن بعدی — نه در برش ezafe)

```sql
ALTER TABLE tenants
  ADD COLUMN monthly_llm_budget_usd numeric NOT NULL DEFAULT 50.0,
  ADD COLUMN llm_key_mode text NOT NULL DEFAULT 'platform'
    CHECK (llm_key_mode IN ('platform', 'byok'));
```

- `monthly_llm_budget_usd`: سقف ماهانهٔ همان مستأجر؛ gateway قبل از هر call چک می‌کند.
- `llm_key_mode`: `platform` = کلید ما؛ `byok` = کلید مشتری (مسیر اختیاری).
- جدول سراسری بودجهٔ شرکت می‌تواند جدا بماند، ولی رد کردن فراخوانی بدون
  سقف tenant ممنوع است.

## پیامد برای llm_gateway (بعداً)
- `complete(..., tenant_id=...)` یا معادل اجباری برای مسیر production.
- انتخاب provider/credential بر اساس `llm_key_mode`.
- ثبت هزینه در `llm_calls` با `tenant_id` (ستون از قبل هست).
