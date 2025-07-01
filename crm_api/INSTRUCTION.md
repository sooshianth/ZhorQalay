# دستورالعمل استفاده از CRM API

این سرویس API برای سیستم CRM جداگانه طراحی شده تا بتواند اطلاعات خریدها را بر اساس شماره تلفن از سیستم ERP دریافت کند.

## منطق دسترسی

سیستم بر اساس شماره تلفن ورودی، خریدها را از سه مسیر پیدا می‌کند:

1. **CRM Access**: خریدهای مشتریانی که شماره تلفن در جدول `CrmAccessNumbers` ثبت شده
2. **Bazaargah Phone**: خریدهایی که `bazaargah_phone_number` آنها برابر با شماره ورودی است
3. **Tahvil Phone**: خریدهایی که `tahvil_phone_number` آنها برابر با شماره ورودی است

سیستم از تکرار خریدها جلوگیری می‌کند و همه خریدهای یکتا را در یک لیست برمی‌گرداند.

## API Endpoints

### 1. بررسی سلامت سرویس
**URL**: `/crm_api/health/`  
**Method**: `GET` یا `POST`

```bash
curl -X GET http://127.0.0.1:8000/crm_api/health/
```

**Response**:
```json
{
    "success": true,
    "status": "healthy",
    "message": "سرویس CRM API به درستی کار می‌کند",
    "statistics": {
        "customers_count": 1250,
        "purchases_count": 3456,
        "crm_access_count": 890
    },
    "version": "2.0",
    "timestamp": "2024-01-15T10:30:45.123456"
}
```

### 2. احراز هویت شماره تلفن
**URL**: `/crm_api/phone-validation/`  
**Method**: `POST`

```bash
curl -X POST http://127.0.0.1:8000/crm_api/phone-validation/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9123456789"
  }'
```

**Response**:
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

### 3. دریافت لیست خریدهای مشتری
**URL**: `/crm_api/customer-purchases/`  
**Method**: `POST`

```bash
curl -X POST http://127.0.0.1:8000/crm_api/customer-purchases/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9123456789"
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
                "created_at": "2024-01-15T08:30:00",
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

### 4. دریافت جزئیات یک خرید
**URL**: `/crm_api/purchase-info/`  
**Method**: `POST`

```bash
curl -X POST http://127.0.0.1:8000/crm_api/purchase-info/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9123456789",
    "purchase_number": "1234567"
  }'
```

**Response**:
```json
{
    "success": true,
    "data": {
        "purchase": {
            "purchase_number": "1234567",
            "invoice_id": "991001",
            "state": "PAYMENT_VERIFIED",
            "state_display": "ثبت خرید در بازارگاه",
            "order_weight": 25000,
            "delivered_weight": 24500,
            "customer_price": 61000,
            "amount_paid": 1500000000,
            "payment_method": "نقدی",
            "buyer_name": "احمد احمدی",
            "address": "تهران، خیابان آزادی",
            "tracking_number": "98765",
            "created_at": "2024-01-15T08:30:00",
            "bazaargah_phone_number": "9123456789",
            "tahvil_phone_number": "9123456789",
            "code_melli_tahvil": "1234567890",
            "extelaf_type": "کسری",
            "extelaf_weight": 500,
            "extelaf_amount": 30500000,
            "is_fully_tasvied": false,
            "is_factored": false,
            "cargo": {
                "cottage": "ذرت آرژانتین",
                "product_type": "corn",
                "product_type_display": "ذرت",
                "country": "argentina",
                "country_display": "آرژانتین"
            }
        },
        "customer": {
            "name": "احمد احمدی",
            "city": "تهران",
            "phone_number": "9123456789",
            "field_of_activity": "مرغدار"
        },
        "barnamehs": [
            {
                "number": "BN123456",
                "serial": "001",
                "shenase_takhsis_code": "ST789012",
                "barnameh_date": "2024-01-16",
                "is_sent_to_bki": true,
                "is_sent_to_bki_at": "2024-01-16T10:00:00"
            }
        ],
        "allocations": [
            {
                "code": "ST789012",
                "weight": 25000
            }
        ]
    }
}
```

## وضعیت‌های خرید

- `INITIATED`: شروع شده
- `SMS_SENT`: پیامک ارسال شده
- `PAYMENT_VERIFIED`: ثبت خرید در بازارگاه
- `ALLOCATION_APPROVED`: ثبت تخصیص در بازارگاه
- `ADDRESS_SENT`: ارسال آدرس به واردکننده
- `WAITING_FOR_BARNAMEH`: در انتظار بارنامه
- `BARNAMEH_INCOMPLETE`: صدور بارنامه (ناقص)
- `BARNAMEH_ISSUED`: صدور بارنامه
- `PURCHASE_CLOSED`: بستن خرید در بازارگاه
- `PAY_KASRI`: پرداخت کسری
- `RECIEIVE_SARAK`: دریافت سرک
- `FULLY_SETTLED`: تسویه کامل
- `INVOICE_ISSUED`: صدور فاکتور
- `CANCELED`: لغو شده
- `ARCHIVED`: آرشیو شده

## نکات مهم

1. شماره تلفن ورودی باید بدون صفر و کد کشور باشد (مثلاً `9123456789`)
2. سیستم خودکار شماره را پاکسازی می‌کند
3. خریدهای تکراری حذف می‌شوند
4. هر خرید نوع دسترسی خود را مشخص می‌کند
5. تمام تاریخ‌ها در فرمت ISO 8601 هستند

## مدیریت خطاها

تمام API ها خطاهای استاندارد HTTP برمی‌گردانند:

- `400`: Bad Request - پارامترهای نامعتبر
- `403`: Forbidden - عدم دسترسی
- `404`: Not Found - یافت نشد
- `500`: Internal Server Error - خطای سرور

```json
{
    "success": false,
    "error": "پیام خطا به فارسی"
}
```