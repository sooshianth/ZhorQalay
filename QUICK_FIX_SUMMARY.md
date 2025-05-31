# ⚡ راه‌حل سریع مشکل Static Files

## 🚨 مشکل شما:
نوبار سمت راست و استایل‌ها روی سرور Production نمایش داده نمی‌شوند.

## 🎯 راه‌حل فوری (5 دقیقه):

### گام 1: فایل‌ها را روی سرور کپی کنید
```
web.config
static_test.html  
fix_iis_static.ps1
```

### گام 2: اجرای اسکریپت PowerShell
```powershell
# در سرور، PowerShell را Run as Administrator کنید:
.\fix_iis_static.ps1
```

### گام 3: Virtual Directory ایجاد کنید
1. IIS Manager باز کنید
2. سایت پروژه > راست‌کلیک > Add Virtual Directory
3. Alias: `static`
4. Path: `C:\inetpub\wwwroot\ZhorQalay\static`

### گام 4: تست کنید
```
http://yourserver.com/static_test.html
http://yourserver.com/static/css/style.css
http://yourserver.com/static/images/3-min.webp
```

## 🔍 اگر هنوز کار نکرد:

### بررسی دسترسی مستقیم:
مستقیماً در مرورگر تایپ کنید:
```
http://yourserver.com/static/css/style.css
```

اگر:
- **404**: Virtual Directory نساخته‌اید
- **403**: مشکل مجوزها
- **500**: مشکل web.config

### بررسی F12 Developer Tools:
1. صفحه سایت را باز کنید
2. F12 > Network > Disable Cache
3. Ctrl+F5 (Hard Refresh)
4. ببینید فایل‌های CSS/JS لود می‌شوند یا خیر

## 📞 پشتیبانی اضطراری:
اگر همچنان مشکل داشتید، این اطلاعات را به تیم فنی بدهید:

1. Screenshot از F12 > Network
2. محتوای Event Viewer > Windows Logs > Application
3. نتیجه اجرای `fix_iis_static.ps1`

**📧 ایمیل:** s.sedaghati@simurgh360.com  
**📞 تلفن:** 3014 360 900 98+

---
**⏰ زمان تخمینی حل مشکل:** 5-10 دقیقه 