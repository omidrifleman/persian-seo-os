# قانون اساسی — Persian SEO OS

**وضعیت:** تصویب‌شده (اجرای `/speckit.constitution` در نشست اول)
**قابل مذاکره:** خیر — تغییر فقط با ADR + تأیید انسانی صریح

## اصول غیرقابل‌مذاکره

### I. پوزیشنینگ human-in-the-loop
محصول «خودکار با تأیید انسانی» است. عبارت «کاملاً خودکار» در کد، UI، مستندات و بازاریابی ممنوع است. سیاست `scaled content abuse` گوگل دقیقاً تولید انبوه بدون نظارت را هدف گرفته است.

### II. گِیت تأیید در دیتابیس
هیچ نوشتنی روی سایت مشتری بدون رکورد `approvals` مجاز نیست. اجبار در لایه داده است (`publish_jobs.approval_id NOT NULL` + FK)، نه در UI و نه در مستندات.

### III. MCP-first
هر قابلیت ابتدا یک MCP tool با ورودی/خروجی تایپ‌شده (Pydantic) است. UI و ایجنت‌ها فقط مصرف‌کننده‌اند.

### IV. ارکستراسیون در کد
مسیر production فقط کد (LangGraph یا معادل + صف کاری). n8n و Dify در production ممنوع‌اند (Sustainable Use / بند منع multi-tenant).

### V. LLM فقط از Gateway
هیچ فراخوانی مستقیم SDK یک LLM provider در کد بیزنس مجاز نیست. تنها مسیر: `services/llm_gateway`.

### VI. تست برای لایه فارسی
هر تابع عمومی در لایه نرمال‌سازی فارسی باید تست واحد داشته باشد؛ کیس‌های شرور (مخلوط فارسی/عربی/لاتین، ایموجی، سه سیستم عددی، idempotency) اجباری‌اند.

### VII. مرز ponytail
سطح `full` مجاز است؛ `ultra` ممنوع. زیرساخت ایمنی از دایره ساده‌سازی خارج است: `approvals`، `snapshot_before`، rollback، `idempotency_key`، `audit_log`، تفکیک `analyze_form`/`display_form`، LLM Gateway، جداسازی منطقی multi-tenant (`tenant_id`). RLS مقدسِ الان نیست — به‌تعویق تا شرط ADR-0003. مرجع: `.cursor/rules/50-skills-workflow.mdc`.

## پیامد برای ایجنت‌ها
- قبل از کد: طرح + Definition of Done + تأیید.
- حدس بیزنسی ممنوع؛ فرض کدی فقط با ثبت در `docs/decisions/ASSUMPTIONS.md`.
- هر پیشنهاد اوپن‌سورس: URL + لایسنس دقیق + تاریخ آخرین کامیت + دلیل.
