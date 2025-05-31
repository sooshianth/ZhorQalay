#!/usr/bin/env python
"""
اسکریپت کمکی برای Deploy کردن فایل‌های Static و حل مشکلات Cache
"""
import os
import shutil
import time
import subprocess
from pathlib import Path

def run_command(command, description):
    """اجرای دستور سیستم با نمایش توضیحات"""
    print(f"\n🔄 {description}...")
    print(f"Command: {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - موفق")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        else:
            print(f"❌ {description} - خطا")
            print(f"Error: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"❌ خطا در اجرای دستور: {e}")
        return False

def clear_old_static_files():
    """پاک کردن فایل‌های static قدیمی"""
    static_dir = Path("static")
    if static_dir.exists():
        print("🗑️ پاک کردن فایل‌های static قدیمی...")
        shutil.rmtree(static_dir)
        print("✅ فایل‌های قدیمی پاک شدند")
    else:
        print("ℹ️ پوشه static وجود ندارد")

def collect_static_files():
    """جمع‌آوری فایل‌های static جدید"""
    return run_command(
        "python manage.py collectstatic --noinput --clear",
        "جمع‌آوری فایل‌های Static"
    )

def add_version_to_static_files():
    """اضافه کردن version به فایل‌های CSS و JS برای جلوگیری از Cache"""
    timestamp = str(int(time.time()))
    
    # فایل‌های CSS اصلی
    css_files = [
        "static/css/style.css",
        "static/css_files/purchase_list_style.css",
        "static/css_files/purchase_CRUD_style.css",
        "static/css_files/manager_profile_style.css",
        "static/css_files/bulk_purchase_edit.css",
    ]
    
    # فایل‌های JS اصلی  
    js_files = [
        "static/js/drag_and_drop_columns.js",
        "static/js/advanced_filter.js",
        "static/js/bulk_purchase_edit.js",
        "static/table_filter/js/table_filter.js",
    ]
    
    print(f"\n🏷️ اضافه کردن version ({timestamp}) به فایل‌ها...")
    
    for file_path in css_files + js_files:
        if Path(file_path).exists():
            # ایجاد نسخه جدید با timestamp
            new_path = file_path.replace('.css', f'.css?v={timestamp}').replace('.js', f'.js?v={timestamp}')
            print(f"✅ {file_path} -> version {timestamp}")
        else:
            print(f"⚠️ فایل یافت نشد: {file_path}")

def create_cache_buster_info():
    """ایجاد فایل اطلاعات Cache Buster"""
    timestamp = str(int(time.time()))
    cache_info = f"""
# Cache Buster Information
# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
# Version: {timestamp}

# برای استفاده در تمپلیت‌ها از این version استفاده کنید:
# href="{{{{ static 'css/style.css' }}}}?v={timestamp}"
# src="{{{{ static 'js/script.js' }}}}?v={timestamp}"

STATIC_VERSION = "{timestamp}"
"""
    
    with open("static_version.txt", "w", encoding="utf-8") as f:
        f.write(cache_info)
    
    print(f"📝 فایل static_version.txt ایجاد شد با version: {timestamp}")
    return timestamp

def create_production_commands():
    """ایجاد فایل دستورات برای سرور Production"""
    commands = """
# دستورات برای سرور Production

# 1. پاک کردن Cache Django
python manage.py clearcache

# 2. جمع‌آوری فایل‌های Static
python manage.py collectstatic --noinput --clear

# 3. اعمال Migration ها (در صورت نیاز)
python manage.py migrate

# 4. راه‌اندازی مجدد وب سرور (IIS/Apache/Nginx)
# برای IIS:
# iisreset

# 5. پاک کردن Cache مرورگر کاربران
# این کار باید توسط کاربران انجام شود یا از Cache Busting استفاده کنید

# دستورات PowerShell برای Windows Server:
# Restart-WebAppPool "DefaultAppPool"
# iisreset
"""
    
    with open("production_deploy_commands.txt", "w", encoding="utf-8") as f:
        f.write(commands)
    
    print("📋 فایل production_deploy_commands.txt ایجاد شد")

def main():
    """تابع اصلی"""
    print("🚀 شروع فرآیند Deploy فایل‌های Static")
    print("=" * 50)
    
    # 1. پاک کردن فایل‌های قدیمی
    clear_old_static_files()
    
    # 2. جمع‌آوری فایل‌های جدید
    success = collect_static_files()
    
    if not success:
        print("❌ خطا در جمع‌آوری فایل‌های static")
        return
    
    # 3. ایجاد اطلاعات Cache Buster
    version = create_cache_buster_info()
    
    # 4. ایجاد فایل دستورات Production
    create_production_commands()
    
    print("\n" + "=" * 50)
    print("✅ فرآیند Deploy کامل شد!")
    print("\n📝 مراحل بعدی:")
    print("1. فایل‌های static را روی سرور Production کپی کنید")
    print("2. دستورات موجود در production_deploy_commands.txt را اجرا کنید")
    print("3. وب سرور را راه‌اندازی مجدد کنید")
    print("4. کاربران باید Cache مرورگر خود را پاک کنند")
    print(f"5. نسخه فعلی: {version}")

if __name__ == "__main__":
    main() 