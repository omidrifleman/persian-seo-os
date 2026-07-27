---
name: approval-gate
description: >
  The mandatory path for any write that leaves our system and touches a
  customer site or external platform. Use whenever the task involves
  publishing, updating meta tags, editing customer content, or any outbound
  mutation.
---

# Approval gate

## مسیر اجباری هر نوشتن بیرونی

```
draft → quality_gate → approvals (انسان) → publish_job (dry_run) → apply → audit_log
                                                              ↓
                                                          rollback
```

هر مرحله را رد کنی، دیتابیس جلویت را می‌گیرد (`approval_id NOT NULL`). این عمدی است.

## چک‌لیست قبل از هر کد انتشار

- [ ] `idempotency_key` یکتا دارد؟ اجرای دوباره باید بی‌اثر باشد، نه دو پست.
- [ ] `snapshot_before` پر می‌شود؟ بدون آن rollback دروغ است.
- [ ] مسیر rollback **تست شده** است؟ تست: ۵۰ صفحه تغییر → همه برگشت.
- [ ] `PUBLISH_DRY_RUN` پیش‌فرض true است؟
- [ ] throttle دامنه اعمال شده؟ درخواست انبوه باید **رد** شود، نه هشدار.
- [ ] `audit_log` می‌نویسد: actor، زمان، diff، دلیل؟
- [ ] گِیت کیفیت: حداقل یک عنصر غیرقابل‌تولید توسط LLM دارد؟ (داده اختصاصی، قیمت واقعی بازار ایران، اسکرین‌شات، نقل‌قول منبع‌دار، تجربه میدانی)

## چرا این قابل حذف نیست

سیاست `scaled content abuse` گوگل دقیقاً تولید انبوه خودکار را هدف گرفته.
تأیید انسانی، هم دفاع الگوریتمی ماست و هم تمایز فروش ما.
اگر این را حذف کنیم، یک ابزار اسپم می‌شویم که دیر یا زود جریمه می‌شود.
