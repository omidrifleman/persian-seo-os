---
name: persian-seo-normalization
description: >
  Rules for handling Persian text in an SEO pipeline: ZWNJ, Arabic yeh/kaf
  unification, ezafe, digit systems, bidi text, and the mandatory separation of
  analyze_form from display_form. Use whenever the task touches Persian
  keywords, titles, meta descriptions, slugs, alt text, or article bodies.
---

# Persian SEO normalization

## قاعده مرکزی: دو فرم، هرگز یکی

| | `analyze_form` | `display_form` |
| --- | --- | --- |
| کاربرد | کلاسترینگ، تطبیق، کلید دیتابیس | متن منتشرشدنی |
| ZWNJ | حذف | اضافه و اصلاح |
| اعداد | ASCII | فارسی |
| نشانه نگارشی | حذف | فارسی‌سازی |

هرگز `analyze_form` را منتشر نکن. هرگز با `display_form` مقایسه نکن.

## ۶ تله‌ای که ایجنت‌ها می‌افتند

1. **ی/ك عربی.** «کيف» و «کیف» دو رشته متفاوت، یک کلمه. اگر یکسان‌سازی نکنی، کلاسترینگ از بنیاد غلط است.
2. **نیم‌فاصله.** «می‌رود» / «میرود» / «می رود» — یک intent، سه رشته.
3. **کسره اضافه (ezafe).** معنای عبارت کلیدی را عوض می‌کند. DadmaTools تشخیص `kasreh` دارد.
4. **سه سیستم عددی.** فارسی (۰-۹)، عربی-هندی (٠-٩)، لاتین. همه باید در analyze یکی شوند.
5. **متن دوجهته.** برند لاتین وسط جمله فارسی رندر را می‌شکند. تست snapshot لازم است.
6. **اسلاگ فارسی.** یا percent-encoding یا لاتین. ترکیب ناسازگار = محتوای تکراری.

## چه چیزی را نباید فرض کنی

- اینکه داده حجم جست‌وجوی فارسی معتبر وجود دارد. وجود ندارد. تخمین را صریح علامت‌گذاری کن.
- اینکه توکنایزرهای انگلیسی‌محور مرز کلمات فارسی را درست می‌زنند.
- اینکه بنچمارک انگلیسی یک مدل، عملکرد فارسی‌اش را پیش‌بینی می‌کند. از Khayyam/PersianMMLU و MIZAN استفاده کن.

## تست اجباری

هر تابع جدید در این لایه باید داشته باشد:
- متن مخلوط فارسی/عربی/لاتین
- ایموجی
- هر سه سیستم عددی در یک رشته
- رشته خالی و فقط‌فاصله
- تست idempotency: `f(f(x)) == f(x)`
