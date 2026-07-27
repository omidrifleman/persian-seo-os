# Persian SEO OS

پلتفرم سئو و مارکتینگ محتوایی مبتنی بر AI برای وب فارسی — با معماری «خودکار با تأیید انسانی».

## شروع سریع
```bash
cp .env.example .env
make install
make test
make up && make migrate
```

## ساختار
```
packages/persian_seo_normalizer/   لایه نرمال‌سازی فارسی (هسته مزیت رقابتی، MIT، قابل انتشار مستقل)
services/llm_gateway/              دروازه واحد LLM: routing / fallback / budget / شمارش توکن
services/audit/                    موتور آدیت سئوی فارسی (اولین محصول قابل فروش)
services/mcp_server/               همه قابلیت‌ها به‌صورت MCP tool
db/migrations/                     اسکیما — گِیت تأیید انسانی در سطح دیتابیس اجبار شده
docs/                              معماری، ADRها، نقشه اسکیل‌ها
.cursor/rules/                     قواعدی که Cursor به‌صورت خودکار به ایجنت تزریق می‌کند
```

## نقشه راه
- **مرحله ۰** ارزیابی build-vs-fork روی OpenSEO
- **مرحله ۱** کتابخانه نرمال‌سازی فارسی (اوپن‌سورس)
- **مرحله ۲** موتور آدیت سئوی فارسی ← اولین درآمد
- **مرحله ۳** LLM Gateway + پایپ‌لاین محتوا با گِیت کیفیت
- **مرحله ۴** صف تأیید انسانی + انتشار وردپرس با rollback
- **مرحله ۵** حلقه بازخورد GSC/GA4 + ماژول GEO/AEO فارسی
