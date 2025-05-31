# اسکریپت حل خودکار مشکلات Static Files در IIS
# باید با دسترسی Administrator اجرا شود

Write-Host "🚀 شروع حل مشکلات Static Files در IIS..." -ForegroundColor Green
Write-Host "=" * 60

# بررسی دسترسی Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ خطا: این اسکریپت باید با دسترسی Administrator اجرا شود" -ForegroundColor Red
    Write-Host "راست‌کلیک روی PowerShell > Run as Administrator" -ForegroundColor Yellow
    pause
    exit 1
}

# متغیرهای پروژه
$projectPath = "C:\inetpub\wwwroot\ZhorQalay"
$staticPath = "$projectPath\static"
$webConfigPath = "$projectPath\web.config"

Write-Host "📂 مسیر پروژه: $projectPath" -ForegroundColor Cyan
Write-Host "📁 مسیر Static: $staticPath" -ForegroundColor Cyan

# بررسی وجود پوشه‌ها
if (-not (Test-Path $projectPath)) {
    Write-Host "❌ پوشه پروژه یافت نشد: $projectPath" -ForegroundColor Red
    pause
    exit 1
}

if (-not (Test-Path $staticPath)) {
    Write-Host "⚠️ پوشه static یافت نشد. در حال ایجاد..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $staticPath -Force
}

# مرحله 1: تنظیم مجوزهای پوشه
Write-Host "`n🔐 مرحله 1: تنظیم مجوزهای پوشه..." -ForegroundColor Green

try {
    # مجوز برای IIS_IUSRS
    icacls $staticPath /grant "IIS_IUSRS:(OI)(CI)R" /T
    Write-Host "✅ مجوز IIS_IUSRS تنظیم شد" -ForegroundColor Green
    
    # مجوز برای Application Pool
    icacls $staticPath /grant "IIS AppPool\DefaultAppPool:(OI)(CI)R" /T
    Write-Host "✅ مجوز Application Pool تنظیم شد" -ForegroundColor Green
    
    # مجوز برای Everyone (فقط خواندن)
    icacls $staticPath /grant "Everyone:(OI)(CI)R" /T
    Write-Host "✅ مجوز Everyone تنظیم شد" -ForegroundColor Green
    
} catch {
    Write-Host "❌ خطا در تنظیم مجوزها: $_" -ForegroundColor Red
}

# مرحله 2: بررسی و تولید web.config
Write-Host "`n📝 مرحله 2: بررسی web.config..." -ForegroundColor Green

$webConfigContent = @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="Python FastCGI" 
      path="*" 
      verb="*" 
      modules="FastCgiModule" 
      scriptProcessor="C:\Python313\python.exe|C:\Python313\Lib\site-packages\wfastcgi.py" 
      resourceType="Unspecified" 
      requireAccess="Script" />
    </handlers>
    
    <!-- Static Files Configuration -->
    <staticContent>
        <mimeMap fileExtension=".css" mimeType="text/css" />
        <mimeMap fileExtension=".js" mimeType="application/javascript" />
        <mimeMap fileExtension=".webp" mimeType="image/webp" />
        <mimeMap fileExtension=".woff" mimeType="font/woff" />
        <mimeMap fileExtension=".woff2" mimeType="font/woff2" />
    </staticContent>
    
    <!-- Static Files Handling -->
    <location path="static">
      <system.webServer>
        <handlers clear="true">
          <add name="StaticFile" path="*" verb="*" modules="StaticFileModule" resourceType="File" requireAccess="Read" />
        </handlers>
      </system.webServer>
    </location>
    
    <!-- Cache Control for Development -->
    <httpProtocol>
      <customHeaders>
        <add name="Cache-Control" value="no-cache, no-store, must-revalidate" />
        <add name="Pragma" value="no-cache" />
        <add name="Expires" value="0" />
      </customHeaders>
    </httpProtocol>
  </system.webServer>

  <appSettings>
    <add key="PYTHONPATH" value="C:\inetpub\wwwroot\ZhorQalay" />
    <add key="WSGI_HANDLER" value="config.wsgi.application" />
    <add key="DJANGO_SETTINGS_MODULE" value="config.settings" />
  </appSettings>
</configuration>
"@

# ایجاد backup از web.config قبلی
if (Test-Path $webConfigPath) {
    $backupPath = "$webConfigPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $webConfigPath $backupPath
    Write-Host "✅ Backup از web.config ایجاد شد: $backupPath" -ForegroundColor Green
}

# نوشتن web.config جدید
$webConfigContent | Out-File -FilePath $webConfigPath -Encoding UTF8
Write-Host "✅ فایل web.config جدید ایجاد شد" -ForegroundColor Green

# مرحله 3: جمع‌آوری Static Files
Write-Host "`n📦 مرحله 3: جمع‌آوری Static Files..." -ForegroundColor Green

try {
    Set-Location $projectPath
    
    # فعال کردن virtual environment (اگر وجود دارد)
    if (Test-Path "venv\Scripts\activate.ps1") {
        & "venv\Scripts\activate.ps1"
        Write-Host "✅ Virtual Environment فعال شد" -ForegroundColor Green
    }
    
    # اجرای collectstatic
    python manage.py collectstatic --noinput --clear
    Write-Host "✅ Static Files جمع‌آوری شد" -ForegroundColor Green
    
} catch {
    Write-Host "❌ خطا در جمع‌آوری Static Files: $_" -ForegroundColor Red
}

# مرحله 4: بررسی وجود فایل‌های مهم
Write-Host "`n🔍 مرحله 4: بررسی فایل‌های مهم..." -ForegroundColor Green

$criticalFiles = @(
    "css\style.css",
    "css_files\purchase_list_style.css",
    "images\3-min.webp",
    "js\drag_and_drop_columns.js",
    "table_filter\css\table_filter.css",
    "table_filter\js\table_filter.js"
)

$missingFiles = @()
foreach ($file in $criticalFiles) {
    $fullPath = Join-Path $staticPath $file
    if (Test-Path $fullPath) {
        $size = (Get-Item $fullPath).Length
        Write-Host "✅ $file ($size bytes)" -ForegroundColor Green
    } else {
        Write-Host "❌ $file - یافت نشد" -ForegroundColor Red
        $missingFiles += $file
    }
}

# مرحله 5: تست IIS Module
Write-Host "`n🔧 مرحله 5: بررسی IIS Modules..." -ForegroundColor Green

try {
    # بررسی StaticFileModule
    $staticModule = Get-WebGlobalModule | Where-Object { $_.Name -eq "StaticFileModule" }
    if ($staticModule) {
        Write-Host "✅ StaticFileModule فعال است" -ForegroundColor Green
    } else {
        Write-Host "❌ StaticFileModule غیرفعال است" -ForegroundColor Red
    }
    
    # بررسی FastCgiModule
    $fastcgiModule = Get-WebGlobalModule | Where-Object { $_.Name -eq "FastCgiModule" }
    if ($fastcgiModule) {
        Write-Host "✅ FastCgiModule فعال است" -ForegroundColor Green
    } else {
        Write-Host "⚠️ FastCgiModule غیرفعال است" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "⚠️ نتوانستیم IIS Modules را بررسی کنیم: $_" -ForegroundColor Yellow
}

# مرحله 6: راه‌اندازی مجدد IIS
Write-Host "`n🔄 مرحله 6: راه‌اندازی مجدد IIS..." -ForegroundColor Green

try {
    # راه‌اندازی مجدد Application Pool
    Restart-WebAppPool "DefaultAppPool"
    Write-Host "✅ Application Pool راه‌اندازی مجدد شد" -ForegroundColor Green
    
    # راه‌اندازی مجدد IIS
    iisreset
    Write-Host "✅ IIS راه‌اندازی مجدد شد" -ForegroundColor Green
    
} catch {
    Write-Host "❌ خطا در راه‌اندازی مجدد IIS: $_" -ForegroundColor Red
}

# نتیجه‌گیری
Write-Host "`n" + "=" * 60
Write-Host "📊 خلاصه نتایج:" -ForegroundColor Cyan

if ($missingFiles.Count -eq 0) {
    Write-Host "✅ همه فایل‌های static موجود هستند" -ForegroundColor Green
} else {
    Write-Host "❌ $($missingFiles.Count) فایل ناموجود:" -ForegroundColor Red
    foreach ($file in $missingFiles) {
        Write-Host "  - $file" -ForegroundColor Red
    }
}

Write-Host "`n📝 مراحل بعدی:" -ForegroundColor Yellow
Write-Host "1. Virtual Directory برای /static در IIS Manager ایجاد کنید" -ForegroundColor White
Write-Host "2. فایل static_test.html را در مرورگر تست کنید" -ForegroundColor White
Write-Host "3. F12 > Network > Disable Cache و صفحه را رفرش کنید" -ForegroundColor White
Write-Host "4. URL های static را مستقیماً تست کنید:" -ForegroundColor White
Write-Host "   - http://yourserver/static/css/style.css" -ForegroundColor Gray
Write-Host "   - http://yourserver/static/images/3-min.webp" -ForegroundColor Gray

Write-Host "`n🎉 اسکریپت تکمیل شد!" -ForegroundColor Green
pause 