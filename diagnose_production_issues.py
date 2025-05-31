#!/usr/bin/env python
"""
اسکریپت تشخیص مشکلات Production Server
"""
import os
import sys
import django
from pathlib import Path

# تنظیم Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

def check_django_settings():
    """بررسی تنظیمات Django"""
    print("🔧 بررسی تنظیمات Django:")
    print(f"   DEBUG: {settings.DEBUG}")
    print(f"   STATIC_URL: {settings.STATIC_URL}")
    print(f"   STATIC_ROOT: {settings.STATIC_ROOT}")
    print(f"   STATICFILES_DIRS: {settings.STATICFILES_DIRS}")
    print(f"   ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    print()

def check_static_files_existence():
    """بررسی وجود فایل‌های static"""
    print("📁 بررسی وجود فایل‌های Static:")
    
    critical_files = [
        'css/style.css',
        'css_files/purchase_list_style.css', 
        'images/3-min.webp',
        'js/drag_and_drop_columns.js',
        'table_filter/css/table_filter.css',
        'table_filter/js/table_filter.js',
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in critical_files:
        # بررسی در STATIC_ROOT
        full_path = os.path.join(settings.STATIC_ROOT, file_path)
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            existing_files.append(f"✅ {file_path} ({file_size} bytes)")
        else:
            missing_files.append(f"❌ {file_path}")
            
        # بررسی با Django static finder
        found = finders.find(file_path)
        if found:
            print(f"   Django Finder: ✅ {file_path} -> {found}")
        else:
            print(f"   Django Finder: ❌ {file_path}")
    
    print("\n📊 خلاصه فایل‌ها:")
    for file in existing_files:
        print(f"   {file}")
    
    if missing_files:
        print("\n🚨 فایل‌های ناموجود:")
        for file in missing_files:
            print(f"   {file}")
    
    return len(missing_files) == 0

def check_static_urls():
    """بررسی URL های static"""
    print("\n🔗 بررسی URL های Static:")
    
    test_files = [
        'css/style.css',
        'images/3-min.webp',
        'css_files/purchase_list_style.css'
    ]
    
    for file_path in test_files:
        url = static(file_path)
        print(f"   {file_path} -> {url}")

def check_directories():
    """بررسی دایرکتوری‌ها"""
    print("\n📂 بررسی دایرکتوری‌ها:")
    
    # بررسی STATIC_ROOT
    if os.path.exists(settings.STATIC_ROOT):
        files_count = len(list(Path(settings.STATIC_ROOT).rglob('*')))
        print(f"   STATIC_ROOT: ✅ {settings.STATIC_ROOT} ({files_count} فایل)")
        
        # نمایش ساختار کلی
        print("   ساختار STATIC_ROOT:")
        for root, dirs, files in os.walk(settings.STATIC_ROOT):
            level = root.replace(str(settings.STATIC_ROOT), '').count(os.sep)
            indent = ' ' * 4 * (level + 1)
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 2)
            for file in files[:3]:  # فقط 3 فایل اول
                print(f"{subindent}{file}")
            if len(files) > 3:
                print(f"{subindent}... و {len(files) - 3} فایل دیگر")
            if level > 2:  # محدود کردن عمق
                break
    else:
        print(f"   STATIC_ROOT: ❌ {settings.STATIC_ROOT} وجود ندارد")
    
    # بررسی STATICFILES_DIRS
    for static_dir in settings.STATICFILES_DIRS:
        if os.path.exists(static_dir):
            files_count = len(list(Path(static_dir).rglob('*')))
            print(f"   STATICFILES_DIR: ✅ {static_dir} ({files_count} فایل)")
        else:
            print(f"   STATICFILES_DIR: ❌ {static_dir} وجود ندارد")

def generate_web_config():
    """تولید فایل web.config برای IIS"""
    web_config = f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="Python FastCGI" 
      path="*" 
      verb="*" 
      modules="FastCgiModule" 
      scriptProcessor="C:\\Python313\\python.exe|C:\\Python313\\Lib\\site-packages\\wfastcgi.py" 
      resourceType="Unspecified" 
      requireAccess="Script" />
    </handlers>
    
    <!-- Static Files Configuration -->
    <staticContent>
        <mimeMap fileExtension=".css" mimeType="text/css" />
        <mimeMap fileExtension=".js" mimeType="application/javascript" />
        <mimeMap fileExtension=".webp" mimeType="image/webp" />
    </staticContent>
    
    <!-- URL Rewrite for Static Files -->
    <rewrite>
      <rules>
        <rule name="Static Files" stopProcessing="true">
          <match url="^static/(.*)" />
          <action type="Rewrite" url="static/{{R:1}}" />
        </rule>
      </rules>
    </rewrite>
    
    <!-- Cache Control -->
    <httpProtocol>
      <customHeaders>
        <add name="Cache-Control" value="no-cache, no-store, must-revalidate" />
        <add name="Pragma" value="no-cache" />
        <add name="Expires" value="0" />
      </customHeaders>
    </httpProtocol>
  </system.webServer>

  <appSettings>
    <add key="PYTHONPATH" value="C:\\inetpub\\wwwroot\\ZhorQalay" />
    <add key="WSGI_HANDLER" value="config.wsgi.application" />
    <add key="DJANGO_SETTINGS_MODULE" value="config.settings" />
  </appSettings>
</configuration>"""
    
    with open("web.config", "w", encoding="utf-8") as f:
        f.write(web_config)
    
    print("📝 فایل web.config جدید ایجاد شد")

def create_static_test_page():
    """ایجاد صفحه تست برای static files"""
    test_html = """<!DOCTYPE html>
<html>
<head>
    <title>Static Files Test</title>
    <link rel="stylesheet" href="/static/css/style.css?v=1748703972">
    <link rel="stylesheet" href="/static/css_files/purchase_list_style.css?v=1748703972">
</head>
<body>
    <h1>Static Files Test</h1>
    <div class="sidebar" style="position: relative; display: block;">
        <div class="sidebar-header">
            <img src="/static/images/3-min.webp?v=1748703972" alt="Logo" class="sidebar-logo">
            <h2 class="sidebar-title">سیمرغ افزار</h2>
        </div>
    </div>
    
    <script src="/static/js/drag_and_drop_columns.js?v=1748703972"></script>
    <script src="/static/table_filter/js/table_filter.js?v=1748703972"></script>
    
    <script>
        // تست بارگذاری فایل‌ها
        window.onload = function() {
            console.log('Page loaded');
            
            // تست CSS
            var cssLoaded = getComputedStyle(document.querySelector('.sidebar')).position;
            console.log('CSS loaded:', cssLoaded !== 'static');
            
            // تست تصاویر
            var img = document.querySelector('img');
            console.log('Image loaded:', img.complete && img.naturalHeight !== 0);
        };
    </script>
</body>
</html>"""
    
    with open("static_test.html", "w", encoding="utf-8") as f:
        f.write(test_html)
    
    print("📄 فایل static_test.html ایجاد شد")

def main():
    """تابع اصلی"""
    print("🔍 تشخیص مشکلات Production Server")
    print("=" * 60)
    
    # 1. بررسی تنظیمات Django
    check_django_settings()
    
    # 2. بررسی دایرکتوری‌ها
    check_directories()
    
    # 3. بررسی وجود فایل‌ها
    files_exist = check_static_files_existence()
    
    # 4. بررسی URL ها
    check_static_urls()
    
    # 5. تولید فایل‌های کمکی
    generate_web_config()
    create_static_test_page()
    
    print("\n" + "=" * 60)
    print("📋 خلاصه تشخیص:")
    
    if files_exist:
        print("✅ فایل‌های static موجود هستند")
        print("🔧 مشکل احتمالی: تنظیمات وب سرور یا مسیردهی")
        print("\n📝 مراحل بعدی:")
        print("1. فایل web.config جدید را روی سرور کپی کنید")
        print("2. static_test.html را در مرورگر باز کنید")
        print("3. F12 > Network > Disable Cache و صفحه را رفرش کنید")
        print("4. خطاهای Console را بررسی کنید")
    else:
        print("❌ برخی فایل‌های static موجود نیستند")
        print("🔧 اول باید: python manage.py collectstatic --noinput --clear")
    
    print("\n🆘 اگر مشکل ادامه دارد:")
    print("- دسترسی‌های فولدر static را بررسی کنید")
    print("- لاگ‌های IIS را چک کنید")
    print("- با تیم فنی تماس بگیرید")

if __name__ == "__main__":
    main() 