# مستندسازی کامل CRM API

## 📋 فهرست مطالب

1. [معرفی کلی](#معرفی-کلی)
2. [منطق کارکرد سیستم](#منطق-کارکرد-سیستم)
3. [نصب و راه‌اندازی](#نصب-و-راه‌اندازی)
4. [API Reference](#api-reference)
5. [مدل‌های داده](#مدل‌های-داده)
6. [مدیریت خطاها](#مدیریت-خطاها)
7. [امنیت](#امنیت)
8. [نمونه‌های استفاده](#نمونه‌های-استفاده)
9. [تست](#تست)
10. [نکات توسعه](#نکات-توسعه)

---

## معرفی کلی

**CRM API** یک سرویس RESTful است که برای سیستم‌های CRM جداگانه طراحی شده تا بتوانند اطلاعات خریدهای مشتریان را بر اساس شماره تلفن از سیستم ERP اصلی دریافت کنند.

### ویژگی‌های کلیدی

- 🔍 **جستجوی هوشمند**: پیدا کردن خریدها از چندین مسیر مختلف
- 📱 **پشتیبانی از فرمت‌های مختلف شماره تلفن**: `09123456789`, `9123456789`, `989123456789`
- 🚫 **حذف تکرار**: جلوگیری از نمایش خریدهای تکراری
- ⚡ **عملکرد بالا**: استفاده از query های بهینه‌شده
- 🔒 **امنیت**: کنترل دسترسی بر اساس شماره تلفن
- 📊 **آمارگیری**: ارائه آمار کامل از دسترسی‌ها

### معماری سیستم

```
┌─────────────────┐    HTTP/JSON    ┌─────────────────┐
│   CRM System    │ ◄──────────────► │   CRM API       │
│   (External)    │                 │   (Django App)  │
└─────────────────┘                 └─────────────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │   ERP Database  │
                                    │   (PostgreSQL)  │
                                    └─────────────────┘
```

---

## منطق کارکرد سیستم

سیستم بر اساس **شماره تلفن ورودی**، خریدها را از **سه مسیر اصلی** پیدا می‌کند:

### 1. CRM Access (مسیر اول)
```sql
-- جستجو در جدول CrmAccessNumbers
SELECT * FROM core_crmaccessnumbers 
WHERE phone_number = 'cleaned_phone' AND customer_id IS NOT NULL;
```
خریدهای تمام مشتریانی که این شماره تلفن دسترسی CRM دارند.

### 2. Bazaargah Phone (مسیر دوم)  
```sql
-- جستجو در فیلد bazaargah_phone_number
SELECT * FROM core_purchase 
WHERE bazaargah_phone_number IN ('9123456789', '09123456789', '989123456789');
```
خریدهایی که شماره تلفن بازارگاه آنها برابر با شماره ورودی است.

### 3. Tahvil Phone (مسیر سوم)
```sql
-- جستجو در فیلد tahvil_phone_number  
SELECT * FROM core_purchase 
WHERE tahvil_phone_number IN ('9123456789', '09123456789', '989123456789');
```
خریدهایی که شماره تلفن تحویل آنها برابر با شماره ورودی است.

### الگوریتم ادغام

```python
# 1. جمع‌آوری ID های یکتا از همه مسیرها
purchase_ids = set()

# 2. اضافه کردن خریدها از هر مسیر
for route in [crm_access, bazaargah_phone, tahvil_phone]:
    purchase_ids.update(route.get_purchase_ids())

# 3. دریافت خریدهای یکتا از دیتابیس
unique_purchases = Purchase.objects.filter(id__in=purchase_ids)
```

---

## نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.8+
- Django 4.0+
- PostgreSQL
- Virtual Environment

### مراحل نصب

1. **کلون پروژه**
```bash
git clone <repository-url>
cd kunqalay
```

2. **فعال‌سازی Virtual Environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac  
source venv/bin/activate
```

3. **نصب Dependencies**
```bash
pip install -r requirements.txt
```

4. **تنظیمات Django**
```bash
python manage.py migrate
python manage.py collectstatic
```

5. **راه‌اندازی سرور**
```bash
python manage.py runserver 127.0.0.1:8000
```

### URL Configuration

در `config/urls.py`:
```python
urlpatterns = [
    # ...
    path('crm-api/', include('crm_api.urls')),
    # ...
]
```

---

## API Reference

### Base URL
```
http://127.0.0.1:8000/crm-api/
```

### 1. Health Check API

**Endpoint**: `GET /health/`

**توضیح**: بررسی وضعیت سلامت سرویس و اتصال به دیتابیس

**Request**:
```bash
curl -X GET "http://127.0.0.1:8000/crm-api/health/"
```

**Response**:
```json
{
    "success": true,
    "status": "healthy",
    "message": "سرویس CRM API به درستی کار می‌کند",
    "statistics": {
        "customers_count": 710,
        "purchases_count": 1368,
        "crm_access_count": 708
    },
    "version": "2.0",
    "timestamp": "2024-01-15T10:30:45.123456+00:00"
}
```

### 2. Phone Validation API

**Endpoint**: `POST /phone-validation/`

**توضیح**: احراز هویت شماره تلفن و بررسی اجازه دسترسی

**Request**:
```bash
curl -X POST "http://127.0.0.1:8000/crm-api/phone-validation/" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "09123456789"
  }'
```

**Response موفق**:
```json
{
    "success": true,
    "data": {
        "phone_number": "9123456789",
        "has_access": true,
        "access_methods": ["CRM Access", "Bazaargah Phone"],
        "customers": [
            {
                "id": 123,
                "name": "احمد احمدی",
                "city": "تهران",
                "access_type": "CRM Access"
            }
        ],
        "statistics": {
            "crm_access_count": 1,
            "bazaargah_purchases_count": 5,
            "tahvil_purchases_count": 2,
            "phone_records_count": 1,
            "legacy_customers_count": 0
        }
    }
}
```

### 3. Customer Purchases API

**Endpoint**: `POST /customer-purchases/`

**توضیح**: دریافت لیست خریدهای یک مشتری بر اساس شماره تلفن

**Request**:
```bash
curl -X POST "http://127.0.0.1:8000/crm-api/customer-purchases/" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "09123456789"
  }'
```

**Response**:
```json
{
    "success": true,
    "data": {
        "phone_number": "9123456789",
        "customers": [
            {
                "name": "احمد احمدی",
                "city": "تهران",
                "phone_number": "9123456789",
                "access_type": "CRM Access"
            }
        ],
        "purchases": [
            {
                "purchase_number": "1234567",
                "invoice_id": "991001",
                "state": "PAYMENT_VERIFIED",
                "state_display": "ثبت خرید در بازارگاه",
                "order_weight": 25000,
                "delivered_weight": 24500,
                "amount_paid": 1500000000,
                "created_at": "2024-01-15T08:30:00+0330",
                "cargo_cottage": "ذرت آرژانتین",
                "customer_name": "احمد احمدی",
                "bazaargah_customer_name": null,
                "access_types": ["CRM Access", "Bazaargah Phone"]
            }
        ],
        "total_purchases": 1,
        "summary": {
            "total_customers_found": 1,
            "crm_access_count": 1,
            "bazaargah_phone_count": 1,
            "tahvil_phone_count": 0
        }
    }
}
```

### 4. Purchase Info API

**Endpoint**: `POST /purchase-info/`

**توضیح**: دریافت جزئیات کامل یک خرید خاص

**Request**:
```bash
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "09123456789",
    "purchase_number": "1234567"
  }'
```

---

## وضعیت‌های خرید

| کد | نام فارسی | توضیح |
|-----|-----------|--------|
| `INITIATED` | شروع شده | خرید ایجاد شده |
| `SMS_SENT` | پیامک ارسال شده | پیامک به مشتری ارسال شد |
| `PAYMENT_VERIFIED` | ثبت خرید در بازارگاه | پرداخت تایید شد |
| `ALLOCATION_APPROVED` | ثبت تخصیص در بازارگاه | تخصیص تایید شد |
| `ADDRESS_SENT` | ارسال آدرس به واردکننده | آدرس ارسال شد |
| `WAITING_FOR_BARNAMEH` | در انتظار بارنامه | منتظر صدور بارنامه |
| `BARNAMEH_INCOMPLETE` | صدور بارنامه (ناقص) | بارنامه ناقص صادر شد |
| `BARNAMEH_ISSUED` | صدور بارنامه | بارنامه کامل صادر شد |
| `PURCHASE_CLOSED` | بستن خرید در بازارگاه | خرید در بازارگاه بسته شد |
| `PAY_KASRI` | پرداخت کسری | در حال پرداخت کسری |
| `RECIEIVE_SARAK` | دریافت سرک | در حال دریافت سرک |
| `FULLY_SETTLED` | تسویه کامل | تسویه نهایی انجام شد |
| `INVOICE_ISSUED` | صدور فاکتور | فاکتور صادر شد |
| `CANCELED` | لغو شده | خرید لغو شد |
| `ARCHIVED` | آرشیو شده | خرید آرشیو شد |

---

## مدیریت خطاها

### HTTP Status Codes

| کد | معنی | استفاده |
|----|------|---------|
| `200` | موفقیت | درخواست موفق |
| `400` | درخواست نامعتبر | پارامترهای اشتباه |
| `403` | عدم دسترسی | شماره تلفن مجاز نیست |
| `404` | یافت نشد | خرید یا مشتری یافت نشد |
| `500` | خطای سرور | مشکل داخلی |

### فرمت خطاها

```json
{
    "success": false,
    "error": "پیام خطا به فارسی"
}
```

---

## نمونه‌های استفاده

### کلاس کامل CRM Client

```python
import requests

class CRMClient:
    def __init__(self, base_url="http://127.0.0.1:8000/crm-api"):
        self.base_url = base_url
        
    def _request(self, endpoint, data=None):
        """درخواست عمومی"""
        url = f"{self.base_url}/{endpoint}/"
        if data:
            response = requests.post(url, json=data)
        else:
            response = requests.get(url)
        return response.json()
    
    def health_check(self):
        """بررسی سلامت سرویس"""
        return self._request("health")
    
    def validate_phone(self, phone_number):
        """احراز هویت شماره تلفن"""
        return self._request("phone-validation", {"phone_number": phone_number})
    
    def get_purchases(self, phone_number):
        """دریافت خریدها"""
        return self._request("customer-purchases", {"phone_number": phone_number})
    
    def get_purchase_info(self, phone_number, purchase_number):
        """جزئیات خرید"""
        return self._request("purchase-info", {
            "phone_number": phone_number,
            "purchase_number": purchase_number
        })

# استفاده
crm = CRMClient()
if crm.health_check()['success']:
    purchases = crm.get_purchases("09123456789")
    print(f"تعداد خریدها: {purchases['data']['total_purchases']}")
```

---

## تست

### فایل‌های تست

1. **`test_api.bat`**: تست کامل همه API ها
2. **`test_customer_purchases.bat`**: تست سریع Customer Purchases

### اجرای تست‌ها

```bash
# تست کامل
cd crm_api/doc
test_api.bat

# تست سریع
test_customer_purchases.bat
```

---

## نکات توسعه

### بهینه‌سازی عملکرد

1. **Database Indexing**:
```sql
CREATE INDEX idx_purchase_bazaargah_phone ON core_purchase(bazaargah_phone_number);
CREATE INDEX idx_purchase_tahvil_phone ON core_purchase(tahvil_phone_number);
CREATE INDEX idx_crm_access_phone ON core_crmaccessnumbers(phone_number);
```

### ساختار فولدر

```
crm_api/
├── __init__.py
├── apps.py
├── urls.py
├── api.py                 # Main API logic
├── doc/
│   ├── test_api.bat       # Complete test
│   └── test_customer_purchases.bat  # Quick test
├── CRM_API_Documentation.md  # This file
└── INSTRUCTION.md         # Quick reference
```

---

## 📞 پشتیبانی

**نسخه**: 2.0  
**آخرین بروزرسانی**: ژانویه 2025  
**سازگاری**: Django 4.0+, Python 3.8+

برای سوالات یا گزارش مشکلات از فایل‌های تست و مستندات موجود استفاده کنید. 