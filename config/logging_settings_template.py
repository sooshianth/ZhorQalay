# تنظیمات لاگ‌گذاری برای پروژه
# این کد را به فایل settings.py اضافه کنید

import os
from pathlib import Path

# مسیر اصلی پروژه
BASE_DIR = Path(__file__).resolve().parent.parent

# ایجاد پوشه logs اگر وجود ندارد
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# تنظیمات لاگ‌گذاری
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'exclude_runserver': {
            '()': 'core.logging_filters.ExcludeRunserverAndHttpProtocol',
        },
    },
    'handlers': {
        # خروجی کنسول برای development
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['exclude_runserver'],
        },
        # فایل لاگ عمومی
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'django.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        # فایل لاگ اختصاصی پیش‌فاکتور
        'proforma_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'proforma_invoice.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        # فایل لاگ خطاها
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'errors.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        # ارسال ایمیل برای خطاهای مهم در production
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # لاگر اصلی Django
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        # لاگر خطاهای Django
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        # لاگر پیش‌فاکتور
        'proforma_invoice': {
            'handlers': ['console', 'proforma_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # لاگر BKI API
        'bki_api_client': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'bki_api_views': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        # لاگر مشتری
        'core_customer': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        # لاگر کلی برای اپلیکیشن
        'general_customer_CRUD_view': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    # لاگر root برای سایر موارد
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# توضیحات:
# ==========
# 1. تمام لاگ‌ها در پوشه logs/ ذخیره می‌شوند
# 2. فایل‌ها به صورت خودکار rotate می‌شوند (حداکثر 10 نسخه)
# 3. لاگ‌های مهم با ایمیل ارسال می‌شوند (فقط در production)
# 4. هر اپلیکیشن می‌تواند لاگر اختصاصی خود را داشته باشد
# 5. لاگ‌های runserver و http_protocol فیلتر می‌شوند برای خوانایی بهتر

# استفاده در کد:
# ===============
# import logging
# logger = logging.getLogger('proforma_invoice')
# logger.info('پیام اطلاعاتی')
# logger.warning('پیام هشدار')
# logger.error('پیام خطا')
# logger.debug('پیام دیباگ')

# نکات مهم:
# ==========
# - در محیط development سطح DEBUG فعال است
# - در محیط production سطح INFO و ERROR فعال است
# - فایل logs/ را به .gitignore اضافه کنید
# - لاگ‌های حساس را هرگز commit نکنید

