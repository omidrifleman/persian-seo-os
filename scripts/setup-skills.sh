#!/usr/bin/env bash
# نصب اسکیل‌های مرحله ۱. دلیل انتخاب هر کدام در SKILLS.md است.
# قبل از اجرا بخوانش. کورکورانه اجرا نکن.
set -euo pipefail

echo "==> 1/4  spec-kit (فرایند اصلی)"
# در ریشه ریپو اجرا کن. --here یعنی در همین پوشه.
uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai cursor

echo "==> 2/4  اسکیل‌های مهندسی"
npx skills@latest add mattpocock/skills
npx skills@latest add DietrichGebert/ponytail

echo "==> 3/4  codebase-memory-mcp (گراف ساختاری کد — ۱۰۰% لوکال)"
curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash

echo "==> 4/4  تمام"
cat <<'NOTE'

کارهای دستی باقی‌مانده:
  1. Cursor را ریستارت کن، بعد بگو: "Index this project"
  2. اسکیل‌های اضافی mattpocock را که لازم نداریم پاک کن
     (triage، teach، wayfinder، improve-codebase-architecture، prototype، resolving-merge-conflicts)
     دلیل: کانتکست محدود است. بعداً هر کدام را لازم شد، برگردان.
  3. اسکیل mcp-builder را از skills.sh اضافه کن.
  4. مرحله ۴ را الان نصب نکن (اسکیل‌های UI/انیمیشن).

NOTE
