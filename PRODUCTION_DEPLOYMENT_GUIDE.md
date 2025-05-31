# راهنمای Deploy کردن تغییرات در سرور Production

## 🚨 مشکلات احتمالی و راه‌حل‌ها

### 1. **مشکل Static Files در Production**

#### علت:
- فایل‌های CSS/JS جدید روی سرور Production کپی نشده‌اند
- Django نتوانسته فایل‌های static را جمع‌آوری کند
- تنظیمات مسیر static files اشتباه است

#### راه‌حل:
```bash
# روی سرور Production:
cd /path/to/your/project

# 1. پاک کردن فایل‌های static قدیمی
rm -rf static/

# 2. جمع‌آوری مجدد فایل‌های static
python manage.py collectstatic --noinput --clear

# 3. تنظیم مجوزها (در Linux/Unix)
chmod -R 755 static/
chown -R www-data:www-data static/

# 4. راه‌اندازی مجدد وب سرور
# برای Apache:
sudo systemctl restart apache2

# برای Nginx:
sudo systemctl restart nginx

# برای IIS (Windows):
iisreset
```

### 2. **مشکل Browser Cache**

#### علت:
- مرورگرها فایل‌های CSS/JS قدیمی را cache کرده‌اند
- فایل‌های جدید بارگذاری نمی‌شوند

#### راه‌حل:
- **Version Parameter اضافه شده:** `?v=1748703972`
- **Cache Headers اضافه شده:** در `<head>` تمپلیت‌ها

```html
<!-- فایل‌های static با version -->
<link rel="stylesheet" href="{% static 'css/style.css' %}?v=1748703972">
<script src="{% static 'js/script.js' %}?v=1748703972"></script>

<!-- Meta tags ضد cache -->
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
```

### 3. **مشکل Git Deployment**

#### مراحل صحیح Deploy:
```bash
# 1. Pull کردن آخرین تغییرات
git pull origin main

# 2. فعال کردن virtual environment
source venv/bin/activate  # Linux/Mac
# یا
venv\Scripts\activate     # Windows

# 3. نصب dependencies جدید (در صورت نیاز)
pip install -r requirements.txt

# 4. اعمال migrations
python manage.py migrate

# 5. جمع‌آوری static files
python manage.py collectstatic --noinput --clear

# 6. راه‌اندازی مجدد سرور
```

### 4. **چک‌لیست Production**

#### قبل از Deploy:
- [ ] تمام تغییرات commit و push شده‌اند
- [ ] فایل‌های static جدید تست شده‌اند
- [ ] Version number بروزرسانی شده است

#### در حین Deploy:
- [ ] Git pull انجام شده
- [ ] Virtual environment فعال است
- [ ] Requirements نصب شده‌اند
- [ ] Migrations اعمال شده‌اند
- [ ] Static files جمع‌آوری شده‌اند
- [ ] مجوزها تنظیم شده‌اند
- [ ] وب سرور راه‌اندازی مجدد شده

#### بعد از Deploy:
- [ ] سایت در مرورگر باز می‌شود
- [ ] استایل‌ها صحیح لود می‌شوند
- [ ] JavaScript کار می‌کند
- [ ] Cache مرورگر پاک شده

## 🛠️ ابزارهای کمکی

### 1. اسکریپت خودکار Deploy
```bash
#!/bin/bash
# deploy.sh

echo "🚀 شروع Deploy..."

# Pull کردن تغییرات
git pull origin main

# فعال کردن virtual environment
source venv/bin/activate

# نصب requirements
pip install -r requirements.txt

# اعمال migrations
python manage.py migrate

# جمع‌آوری static files
python manage.py collectstatic --noinput --clear

# راه‌اندازی مجدد سرور
sudo systemctl restart nginx
sudo systemctl restart gunicorn  # یا uwsgi

echo "✅ Deploy کامل شد!"
```

### 2. تست Static Files
```python
# test_static.py
import os
from django.conf import settings

def test_static_files():
    """تست وجود فایل‌های static مهم"""
    important_files = [
        'css/style.css',
        'css_files/purchase_list_style.css',
        'js/drag_and_drop_columns.js',
        'images/3-min.webp',
    ]
    
    missing_files = []
    
    for file_path in important_files:
        full_path = os.path.join(settings.STATIC_ROOT, file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ فایل‌های ناموجود:")
        for file in missing_files:
            print(f"  - {file}")
    else:
        print("✅ همه فایل‌های static موجود هستند")

if __name__ == "__main__":
    test_static_files()
```

## 🔧 تنظیمات سرور

### Apache (.htaccess)
```apache
# Cache static files for 1 year
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/jpg "access plus 1 year"
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
</IfModule>

# Force reload for HTML files
<FilesMatch "\.(html|htm)$">
    Header set Cache-Control "no-cache, no-store, must-revalidate"
    Header set Pragma "no-cache"
    Header set Expires 0
</FilesMatch>
```

### Nginx
```nginx
# در فایل nginx.conf یا site config
location /static/ {
    alias /path/to/your/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location / {
    # تنظیمات Django
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    
    # No cache for HTML
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    add_header Expires "0";
}
```

## 📞 پشتیبانی

اگر بعد از انجام این مراحل هنوز مشکل دارید:

1. **بررسی لاگ‌های سرور:**
   ```bash
   # Apache
   tail -f /var/log/apache2/error.log
   
   # Nginx
   tail -f /var/log/nginx/error.log
   
   # Django
   tail -f debug.log
   ```

2. **تست در مرورگر:**
   - F12 > Network > Disable Cache
   - Ctrl+F5 (Hard Refresh)
   - Ctrl+Shift+Delete (Clear Cache)

3. **تماس با تیم فنی:**
   - ایمیل: s.sedaghati@simurgh360.com
   - تلفن: 3014 360 900 98+

## 🔄 آپدیت Version

برای آپدیت version در آینده:

1. در فایل `deploy_static_files.py` اجرا کنید
2. Version جدید را در تمپلیت‌ها اعمال کنید
3. مراحل deploy را تکرار کنید

**نسخه فعلی:** `1748703972` (2025-01-28) 