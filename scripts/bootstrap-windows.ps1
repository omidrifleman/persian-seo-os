# bootstrap-windows.ps1
# نصب ابزارهای پایه روی یک ویندوز تازه‌نصب.
# قبل از setup-skills.ps1 اجرا می‌شود. یک بار کافی است.
# اجرا:  powershell -ExecutionPolicy Bypass -File scripts\bootstrap-windows.ps1

$ErrorActionPreference = "Continue"

Write-Host "`n=== بررسی winget ===" -ForegroundColor Cyan
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget نیست. از Microsoft Store برو سراغ 'App Installer' و نصب/به‌روز کن،" -ForegroundColor Red
    Write-Host "یا از https://aka.ms/getwinget بگیر. بعد این اسکریپت را دوباره اجرا کن." -ForegroundColor Red
    exit 1
}

# شناسه‌های winget. اگر یکی پیدا نشد:  winget search <نام>
$packages = @(
    @{ Id = "Git.Git";              Name = "Git";              Need = $true  },
    @{ Id = "Python.Python.3.12";   Name = "Python 3.12";      Need = $true  },
    @{ Id = "OpenJS.NodeJS.LTS";    Name = "Node.js LTS";      Need = $true  },
    @{ Id = "astral-sh.uv";         Name = "uv";               Need = $true  },
    @{ Id = "Microsoft.PowerShell"; Name = "PowerShell 7";     Need = $true  },
    @{ Id = "Anysphere.Cursor";     Name = "Cursor";           Need = $true  },
    @{ Id = "GitHub.cli";           Name = "GitHub CLI";       Need = $false },
    @{ Id = "7zip.7zip";            Name = "7-Zip";            Need = $false }
)

$failed = @()
foreach ($p in $packages) {
    Write-Host "`n=== نصب $($p.Name)  [$($p.Id)] ===" -ForegroundColor Cyan
    winget install -e --id $p.Id --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        # کد -1978335189 یعنی از قبل نصب است — خطا نیست.
        if ($LASTEXITCODE -eq -1978335189) {
            Write-Host "از قبل نصب بوده." -ForegroundColor DarkGray
        } else {
            Write-Host "ناموفق (exit $LASTEXITCODE)" -ForegroundColor Yellow
            $failed += $p
        }
    }
}

Write-Host "`n=== تنزیم نام و ایمیل Git ===" -ForegroundColor Cyan
Write-Host "اگر قبلاً تنزیم نکرده‌ای، این دو خط را دستی بزن:" -ForegroundColor DarkGray
Write-Host '  git config --global user.name "Your Name"' -ForegroundColor DarkGray
Write-Host '  git config --global user.email "you@example.com"' -ForegroundColor DarkGray
Write-Host "  git config --global core.autocrlf input   # مهم: تست‌های نرمال‌سازی فارسی را از CRLF مصون می‌کند" -ForegroundColor DarkGray

if ($failed.Count -gt 0) {
    Write-Host "`n=== موارد ناموفق ===" -ForegroundColor Red
    foreach ($p in $failed) { Write-Host "  - $($p.Name)  →  winget search $($p.Name)" -ForegroundColor Red }
}

@"

=======================================================
مرحله بعد — دقیقاً به این ترتیب:

  1. این پنجره PowerShell را ببند و یکی تازه باز کن.
     (بدون این کار PATH تازه دیده نمی‌شود و git/python را پیدا نمی‌کند)

  2. بررسی کن همه نصب شده‌اند:
       git --version ; python --version ; node --version ; npm --version ; uv --version

  3. گیت را راه بینداز:
       git init
       git add -A
       git commit -m "chore: scaffold"

  4. تست‌ها را بگیر (باید ۳۶ تا پاس شود، بدون هیچ نصب اضافه):
       python -m unittest discover -s packages -p "test_*.py" -v

  5. اسکیل‌ها:
       powershell -ExecutionPolicy Bypass -File scripts\setup-skills.ps1

  6. cursor .

فعلاً لازم نیست: Docker، Postgres، Redis، وردپرس لوکال.
اولین کار مهندسی (لایه ezafe) فقط پایتون می‌خواهد.
=======================================================

"@ | Write-Host -ForegroundColor Green
