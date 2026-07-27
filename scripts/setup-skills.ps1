# نسخه ویندوزی setup-skills.sh — در PowerShell اجرا کن.
# دلیل انتخاب هر اسکیل در SKILLS.md است. قبل از اجرا بخوانش.
$ErrorActionPreference = "Stop"

Write-Host "==> 0/4  بررسی پیش‌نیازها" -ForegroundColor Cyan
foreach ($cmd in @("git", "node", "python")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd پیدا نشد. اول نصبش کن."
    }
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv پیدا نشد. نصب می‌کنم..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
}

Write-Host "==> 1/4  spec-kit (فرایند اصلی)" -ForegroundColor Cyan
uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai cursor

Write-Host "==> 2/4  اسکیل‌های مهندسی" -ForegroundColor Cyan
npx skills@latest add mattpocock/skills
npx skills@latest add DietrichGebert/ponytail

Write-Host "==> 3/4  codebase-memory-mcp (گراف ساختاری کد — ۱۰۰% لوکال)" -ForegroundColor Cyan
Write-Host "این مرحله یک اسکریپت از اینترنت می‌گیرد. اگر نمی‌خواهی، با Ctrl+C بزن بیرون" -ForegroundColor Yellow
Write-Host "و دستی از مخزن رسمی نصب کن:  winget install DeusData.codebase-memory-mcp" -ForegroundColor Yellow
Write-Host "یا:  scoop install codebase-memory-mcp" -ForegroundColor Yellow
Read-Host "برای ادامه Enter بزن"
# مسیر install.ps1 را خودت در مخزن تأیید کن قبل از اجرا:
# https://github.com/DeusData/codebase-memory-mcp
irm https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.ps1 | iex

Write-Host "==> 4/4  تمام" -ForegroundColor Green
@"

کارهای دستی باقی‌مانده:
  1. Cursor را ریستارت کن، بعد بگو: "Index this project"
  2. اسکیل‌های اضافی mattpocock را که لازم نداریم پاک کن
     (triage، teach، wayfinder، improve-codebase-architecture، prototype، resolving-merge-conflicts)
  3. اسکیل mcp-builder را از skills.sh اضافه کن.
  4. مرحله ۴ را الان نصب نکن (اسکیل‌های UI/انیمیشن).
  5. فایل‌های SKILL.md نصب‌شده را یک بار بخوان (ریسک prompt injection).

"@ | Write-Host
