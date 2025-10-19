# Circular Buffer Handler for Logging

این سیستم یک handler لاگینگ سفارشی است که تمامی لاگ‌های سطح DEBUG و بالاتر را در حافظه نگه‌داری می‌کند و امکان دسترسی به آن‌ها را از طریق پنل ادمین Django فراهم می‌آورد.

## ویژگی‌ها

- ✅ نگه‌داری لاگ‌ها در حافظه با استفاده از Circular Buffer (بافر دایره‌ای)
- ✅ Thread-safe و بدون مشکل در محیط‌های multi-threaded
- ✅ ظرفیت قابل تنظیم (پیش‌فرض: 5000 لاگ)
- ✅ فیلتر کردن بر اساس سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- ✅ فیلتر کردن بر اساس نام logger
- ✅ محدود کردن تعداد لاگ‌های نمایش داده شده
- ✅ نمایش آمار کامل از لاگ‌ها
- ✅ امکان پاک کردن لاگ‌ها توسط superuser
- ✅ رابط کاربری فارسی و زیبا در پنل ادمین

## معماری

### فایل‌های اصلی

1. **`core/logging_filters.py`**
   - کلاس `CircularBufferHandler`: Handler اصلی که لاگ‌ها را در حافظه نگه می‌دارد
   - Singleton pattern برای اطمینان از وجود یک نمونه واحد
   - متدهای `get_logs()`, `get_stats()`, `clear()`

2. **`core/LogViewerModel.py`**
   - مدل ساده برای نمایش در پنل ادمین (بدون جدول دیتابیس)
   - فقط برای ایجاد نقطه ورود در پنل ادمین استفاده می‌شود

3. **`core/admin.py`**
   - کلاس `LogViewerAdmin`: نمایش و مدیریت لاگ‌ها در پنل ادمین
   - Override کردن `changelist_view` برای نمایش سفارشی

4. **`core/templates/admin/log_viewer.html`**
   - قالب HTML برای نمایش لاگ‌ها
   - شامل فیلترها، جدول لاگ‌ها، و آمار

5. **`config/settings.py`**
   - تنظیمات لاگینگ Django
   - اضافه شدن handler `circular_buffer` به تمامی logger ها

## نحوه استفاده

### 1. مشاهده لاگ‌ها در پنل ادمین

1. سرور را راه‌اندازی کنید:
   ```bash
   python manage.py runserver
   ```

2. وارد پنل ادمین شوید:
   ```
   http://127.0.0.1:8000/admin/
   ```

3. در بخش **CORE** به **نمایشگر لاگ‌ها** بروید

### 2. فیلتر کردن لاگ‌ها

در صفحه نمایشگر لاگ‌ها می‌توانید:

- **سطح لاگ را انتخاب کنید**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Logger خاصی را انتخاب کنید**: مثلاً `bki_api_client`, `core_admin`
- **تعداد لاگ‌های نمایشی را تعیین کنید**: از 1 تا 5000

### 3. استفاده در کد

```python
import logging

# ایجاد logger
logger = logging.getLogger('my_logger_name')

# لاگ کردن
logger.debug("پیام DEBUG")
logger.info("پیام INFO")
logger.warning("پیام WARNING")
logger.error("پیام ERROR")
```

### 4. دسترسی برنامه‌نویسی به لاگ‌ها

```python
from core.logging_filters import CircularBufferHandler

# دریافت handler
handler = CircularBufferHandler()

# دریافت تمامی لاگ‌ها
all_logs = handler.get_logs()

# دریافت لاگ‌های با سطح ERROR
error_logs = handler.get_logs(level='ERROR')

# دریافت لاگ‌های یک logger خاص
bki_logs = handler.get_logs(logger_name='bki_api_client')

# دریافت 100 لاگ اخیر
recent_logs = handler.get_logs(limit=100)

# دریافت آمار
stats = handler.get_stats()
print(f"تعداد کل لاگ‌ها: {stats['total']}")
print(f"لاگ‌های ERROR: {stats['levels'].get('ERROR', 0)}")

# پاک کردن لاگ‌ها
handler.clear()
```

## تنظیمات

### تغییر ظرفیت بافر

در فایل `config/settings.py`:

```python
'handlers': {
    'circular_buffer': {
        'level': 'DEBUG',
        'class': 'core.logging_filters.CircularBufferHandler',
        'capacity': 10000,  # تغییر ظرفیت به 10000 لاگ
        'formatter': 'verbose',
    },
    # ...
}
```

### اضافه کردن handler به logger جدید

```python
'loggers': {
    'my_new_logger': {
        'handlers': ['console', 'file', 'circular_buffer'],
        'level': 'DEBUG',
        'propagate': False,
    },
}
```

## تست

برای تست کارکرد handler، فایل `test_circular_buffer.py` را اجرا کنید:

```bash
python test_circular_buffer.py
```

این اسکریپت:
- 20 لاگ تستی ایجاد می‌کند
- آمار لاگ‌ها را نمایش می‌دهد
- لاگ‌های ERROR را فیلتر می‌کند
- 5 لاگ اخیر را نمایش می‌دهد

## مزایا

1. **عملکرد بالا**: لاگ‌ها در حافظه نگه‌داری می‌شوند (بدون I/O دیسک)
2. **مصرف حافظه ثابت**: Circular buffer اطمینان می‌دهد که حافظه overflow نمی‌شود
3. **Thread-safe**: با استفاده از Lock برای دسترسی همزمان محافظت شده است
4. **Singleton**: فقط یک نمونه از handler وجود دارد
5. **فیلترهای قدرتمند**: امکان فیلتر بر اساس level، logger، و limit
6. **رابط کاربری ساده**: مشاهده آسان لاگ‌ها از پنل ادمین

## محدودیت‌ها

1. **حافظه موقت**: لاگ‌ها فقط تا زمان اجرای سرور نگه‌داری می‌شوند
2. **ظرفیت محدود**: فقط تعداد مشخصی لاگ در حافظه است
3. **یک Process**: در محیط multi-process (مثل Gunicorn) هر process بافر جداگانه‌ای دارد

## نکات امنیتی

- فقط کاربران superuser می‌توانند لاگ‌ها را پاک کنند
- دسترسی به لاگ‌ها فقط از طریق پنل ادمین Django امکان‌پذیر است
- تمامی درخواست‌های پاک کردن لاگ لاگ می‌شوند (برای audit)

## توسعه آینده

- [ ] Export لاگ‌ها به فایل
- [ ] جستجوی متنی در لاگ‌ها
- [ ] نمودار آماری لاگ‌ها
- [ ] Real-time update با WebSocket
- [ ] پشتیبانی از Redis برای sharing بین process ها

## نویسنده

این ماژول برای پروژه CRM توسعه داده شده است.

تاریخ: اکتبر 2025
