"""
Test script for CircularBufferHandler

این اسکریپت برای تست کارکرد CircularBufferHandler استفاده می‌شود.
"""
import os
import sys

# اضافه کردن مسیر پروژه به path
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# تنظیم Django settings قبل از import کردن هر چیز دیگری
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import logging
from core.logging_filters import CircularBufferHandler

# دریافت handler
handler = CircularBufferHandler()

print("=" * 80)
print("تست CircularBufferHandler")
print("=" * 80)
print()

# ایجاد چند لاگ تستی
loggers = [
    'test_logger_1',
    'test_logger_2',
    'bki_api_client',
    'core_admin',
]

levels = [
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
]

print("ایجاد لاگ‌های تستی...")
for i in range(20):
    logger_name = loggers[i % len(loggers)]
    level = levels[i % len(levels)]
    
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    if level == logging.DEBUG:
        logger.debug(f"پیام تستی DEBUG شماره {i+1}")
    elif level == logging.INFO:
        logger.info(f"پیام تستی INFO شماره {i+1}")
    elif level == logging.WARNING:
        logger.warning(f"پیام تستی WARNING شماره {i+1}")
    elif level == logging.ERROR:
        logger.error(f"پیام تستی ERROR شماره {i+1}")

print(f"تعداد {i+1} لاگ ایجاد شد.")
print()

# نمایش آمار
stats = handler.get_stats()
print("آمار لاگ‌ها:")
print(f"  تعداد کل: {stats['total']}")
print(f"  ظرفیت: {stats['capacity']}")
print()

print("تعداد لاگ‌ها به تفکیک سطح:")
for level, count in stats['levels'].items():
    print(f"  {level}: {count}")
print()

print("تعداد لاگ‌ها به تفکیک logger:")
for logger_name, count in stats['loggers'].items():
    print(f"  {logger_name}: {count}")
print()

# دریافت لاگ‌های با سطح ERROR
print("-" * 80)
print("لاگ‌های با سطح ERROR:")
error_logs = handler.get_logs(level='ERROR')
for log in error_logs:
    print(f"  [{log['timestamp']}] {log['logger']}: {log['message']}")
print()

# دریافت 5 لاگ اخیر
print("-" * 80)
print("5 لاگ اخیر:")
recent_logs = handler.get_logs(limit=5)
for log in recent_logs:
    print(f"  [{log['timestamp']}] {log['level']} - {log['logger']}: {log['message']}")
print()

# دریافت لاگ‌های یک logger خاص
print("-" * 80)
print("لاگ‌های logger 'bki_api_client':")
bki_logs = handler.get_logs(logger_name='bki_api_client')
for log in bki_logs:
    print(f"  [{log['timestamp']}] {log['level']}: {log['message']}")
print()

print("=" * 80)
print("تست با موفقیت انجام شد!")
print("=" * 80)
print()
print("برای مشاهده لاگ‌ها در پنل ادمین:")
print("1. سرور را راه‌اندازی کنید")
print("2. وارد پنل ادمین شوید")
print("3. به قسمت 'نمایشگر لاگ‌ها' بروید")
print()
