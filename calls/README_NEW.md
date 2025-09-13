# Call Management System with Asterisk Integration

این ماژول برای مدیریت تماس‌های اتوماتیک با قابلیت اتصال به Asterisk طراحی شده است.

## ویژگی‌های جدید

### 1. صف تماس (Call Queue)
- امکان ایجاد صف بزرگ شماره‌های تلفن قبل از شروع تماس
- قابلیت افزودن شماره‌ها از منابع مختلف:
  - مشتریان موجود (جستجو بر اساس نام یا شماره)
  - ورودی دستی شماره‌ها
  - آپلود فایل اکسل
  - پیشنهادات سیستم

### 2. اتصال به Asterisk
- پشتیبانی از API کال سنتر Asterisk
- امکان ارسال درخواست به صورت JSON
- پیکربندی URL و API Key
- ثبت لاگ تمام فعالیت‌ها

### 3. مدل‌های اصلی

#### CallQueue
```python
class CallQueue(models.Model):
    session_id = models.CharField(max_length=100)  # شناسه جلسه کاری
    phone_number = models.CharField(max_length=20)  # شماره تلفن
    customer = models.ForeignKey(Customer)  # مشتری (اختیاری)
    source = models.CharField(max_length=20)  # منبع (مشتری/دستی/اکسل/پیشنهادی)
    added_by = models.ForeignKey(User)  # کاربر اضافه کننده
    created_at = models.DateTimeField(auto_now_add=True)
```

#### AutomaticCall (بروزرسانی شده)
```python
class AutomaticCall(models.Model):
    # فیلدهای قبلی +
    asterisk_api_url = models.CharField(max_length=200)  # آدرس API
    asterisk_api_key = models.CharField(max_length=100)  # کلید API
    queue_session_id = models.CharField(max_length=100)  # ارجاع به صف
    
    def start_asterisk_call(self):
        """شروع تماس از طریق Asterisk API"""
```

## نحوه استفاده

### 1. ایجاد تماس جدید
1. به صفحه "ایجاد تماس اتوماتیک" بروید
2. در بخش "صف تماس‌ها" شماره‌ها را اضافه کنید:
   - **تب مشتریان**: جستجو و انتخاب مشتریان موجود
   - **تب دستی**: وارد کردن شماره‌ها به صورت متنی
   - **تب اکسل**: آپلود فایل Excel حاوی شماره‌ها
   - **تب پیشنهادی**: اضافه کردن شماره‌های پیشنهادی سیستم
3. فرم اصلی را پر کنید (عنوان، نوع، زمان، ...)
4. تنظیمات Asterisk را وارد کنید
5. "ایجاد تماس اتوماتیک" را کلیک کنید

### 2. شروع تماس با Asterisk
1. در صفحه جزئیات تماس، دکمه "شروع تماس Asterisk" را کلیک کنید
2. سیستم درخواست زیر را به API ارسال می‌کند:

```bash
curl -X POST http://192.168.100.128:5000/api/start-dialer \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: YourSuperSecretKeyGoesHere" \
     -d '{ "numbers": ["9123456789", "9876543210", "9111222333"] }'
```

### 3. مدیریت صف
- امکان حذف شماره‌های تکی از صف
- مشاهده آمار صف (تعداد کل، مشتریان، دستی)
- حفظ صف تا زمان ایجاد تماس نهایی
- پشتیبانی از جلسات کاری (Session)

## API های موجود

### Queue Management APIs
- `POST /api/queue/add-customer/` - افزودن مشتری به صف
- `POST /api/queue/add-manual/` - افزودن شماره‌های دستی
- `POST /api/queue/upload-excel/` - آپلود فایل اکسل
- `POST /api/queue/add-suggestions/` - افزودن پیشنهادات
- `POST /api/queue/remove/` - حذف از صف
- `GET /api/customers/search/` - جستجوی مشتریان

### Call Management APIs
- `POST /automatic/<id>/start-asterisk/` - شروع تماس با Asterisk

## تنظیمات مورد نیاز

### Python Packages
```bash
pip install pandas openpyxl requests
```

### Django Settings
```python
INSTALLED_APPS = [
    # ...
    'calls',
]
```

## ساختار فایل‌ها

```
calls/
├── models.py           # CallQueue, AutomaticCall بروزرسانی شده
├── views.py           # View های صف و Asterisk
├── admin.py           # مدیریت CallQueue در ادمین
├── urls.py            # URL های جدید
└── templates/calls/
    └── create_automatic_call.html  # صفحه ایجاد با صف
```

## مثال استفاده از API

### درخواست Asterisk
```python
import requests
import json

# آماده‌سازی داده‌ها
headers = {
    'Content-Type': 'application/json',
    'X-API-KEY': 'YourSuperSecretKeyGoesHere'
}

data = {
    'numbers': ['9123456789', '9876543210']
}

# ارسال درخواست
response = requests.post(
    'http://192.168.100.128:5000/api/start-dialer',
    headers=headers,
    data=json.dumps(data)
)

if response.status_code == 200:
    print("تماس با موفقیت شروع شد")
else:
    print(f"خطا: {response.status_code}")
```

## لاگ‌ها

تمام فعالیت‌های مربوط به Asterisk در جدول `CallLog` ثبت می‌شود:
- شروع تماس
- خطاهای API
- پاسخ‌های دریافتی

## توسعه آینده

- [ ] پشتیبانی از فرمت‌های بیشتر Excel
- [ ] فیلترینگ پیشرفته مشتریان
- [ ] گزارش‌گیری از نتایج تماس‌ها
- [ ] اتصال مستقیم به AMI Asterisk
- [ ] پشتیبانی از تماس‌های زمان‌بندی شده
