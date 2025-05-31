# راهنمای حل مشکل Static Files در IIS

## 🚨 علت اصلی مشکل

مشکل شما مربوط به **تنظیمات IIS** است که فایل‌های static را به درستی serve نمی‌کند.

## 🛠️ راه‌حل‌های قدم به قدم

### مرحله 1: تنظیم مجوزهای پوشه

```cmd
# در Command Prompt سرور (Run as Administrator):
cd C:\inetpub\wwwroot\ZhorQalay

# دادن مجوز خواندن به IIS_IUSRS
icacls static /grant IIS_IUSRS:(OI)(CI)R
icacls static /grant "IIS AppPool\DefaultAppPool":(OI)(CI)R

# بررسی مجوزها
icacls static
```

### مرحله 2: تنظیم Virtual Directory برای Static Files

1. باز کردن **IIS Manager**
2. راه‌رفتن به سایت پروژه
3. راست‌کلیک > **Add Virtual Directory**
4. تنظیمات:
   - **Alias:** `static`
   - **Physical path:** `C:\inetpub\wwwroot\ZhorQalay\static`
5. کلیک **OK**

### مرحله 3: اعمال web.config جدید

فایل `web.config` جدید ایجاد شده را روی سرور کپی کنید:

```xml
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
```

### مرحله 4: بررسی MIME Types

در IIS Manager:
1. انتخاب سایت
2. دابل‌کلیک روی **MIME Types**
3. اطمینان از وجود:
   - `.css` → `text/css`
   - `.js` → `application/javascript`
   - `.webp` → `image/webp`

### مرحله 5: تست Static Files

1. فایل `static_test.html` را در مرورگر باز کنید:
   ```
   http://yourserver.com/static_test.html
   ```

2. F12 > Network > بررسی کنید که فایل‌های زیر لود می‌شوند:
   - `/static/css/style.css?v=1748703972`
   - `/static/css_files/purchase_list_style.css?v=1748703972`
   - `/static/images/3-min.webp?v=1748703972`

### مرحله 6: راه‌اندازی مجدد IIS

```cmd
# در Command Prompt (Run as Administrator):
iisreset

# یا در PowerShell:
Restart-WebAppPool "DefaultAppPool"
```

## 🔍 تشخیص مشکل

### بررسی دسترسی مستقیم

مستقیماً این URL ها را در مرورگر تست کنید:

```
http://yourserver.com/static/css/style.css
http://yourserver.com/static/images/3-min.webp
http://yourserver.com/static/css_files/purchase_list_style.css
```

### بررسی خطاها

1. **Event Viewer** را باز کنید
2. **Windows Logs** > **Application**
3. فیلتر روی **IIS** و خطاهای مربوط به static files

### کدهای خطای رایج

- **404 Not Found**: Virtual Directory تنظیم نشده
- **403 Forbidden**: مشکل مجوزها
- **500 Internal Server Error**: مشکل web.config

## 🚀 اسکریپت خودکار

```powershell
# fix_iis_static.ps1
Write-Host "🔧 حل مشکل Static Files در IIS..."

# تنظیم مجوزها
icacls "C:\inetpub\wwwroot\ZhorQalay\static" /grant "IIS_IUSRS:(OI)(CI)R"
icacls "C:\inetpub\wwwroot\ZhorQalay\static" /grant "IIS AppPool\DefaultAppPool:(OI)(CI)R"

# راه‌اندازی مجدد IIS
iisreset

Write-Host "✅ تنظیمات اعمال شد. Virtual Directory را دستی اضافه کنید."
```

## 📋 چک‌لیست نهایی

- [ ] مجوزهای پوشه static تنظیم شده
- [ ] Virtual Directory برای `/static` ایجاد شده
- [ ] فایل web.config جدید کپی شده
- [ ] MIME Types بررسی شده‌اند
- [ ] IIS راه‌اندازی مجدد شده
- [ ] تست مستقیم URL های static انجام شده
- [ ] F12 > Network > خطاها بررسی شده‌اند

## 🆘 اگر هنوز کار نمی‌کند

1. **بررسی Application Pool:**
   - .NET Framework Version
   - Identity تنظیمات

2. **بررسی Site Bindings:**
   - Port و IP صحیح باشد

3. **تماس با تیم فنی:**
   - لاگ‌های IIS را ضمیمه کنید
   - Screenshot از خطاهای F12

---

**⚡ نکته مهم:** بعد از هر تغییر، حتماً `iisreset` کنید و cache مرورگر را پاک کنید (Ctrl+F5). 