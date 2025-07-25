# Customer Server Filter Debug Guide

## مشکلات فعلی:
1. ستون‌های خالی (شهر، حوزه فعالیت)
2. عدم تطابق ستون‌ها با سرستون‌ها
3. ستون‌هایی که در انتهای جدول ظاهر می‌شوند

## مراحل Debug:

### مرحله 1: بررسی Backend
1. بررسی کنید که آیا داده‌ها در دیتابیس وجود دارند
2. بررسی کنید که آیا view درست کار می‌کند

### مرحله 2: بررسی Frontend
1. بررسی کنید که آیا JavaScript درست headers را می‌بیند
2. بررسی کنید که آیا ترتیب ستون‌ها درست است

## تغییرات اعمال شده:

### در View (customer_list_view.py):
- اصلاح field_of_activity به صورت ManyToMany
- اصلاح purchase_preferences و product_preferences
- اضافه کردن debug logging

### در JavaScript (customer_server_filter.js):
- اصلاح createTableRow برای رعایت ترتیب DOM
- اضافه کردن console logging
- حل مشکل ستون‌های مخفی

## نکات مهم:

1. ترتیب ستون‌ها در template:
   - selection
   - is_favorite  
   - name
   - phone_number
   - city
   - field_of_activity
   - purchase_count
   - total_purchase_weight
   - purchase_preferences (مخفی)
   - product_preferences (مخفی)
   - last_purchase_date (مخفی)
   - actions

2. برخی ستون‌ها با `style="display: none;"` مخفی هستند

3. JavaScript باید ترتیب دقیق headers در DOM را رعایت کند

## آزمایش:
1. باز کردن Developer Tools -> Console
2. مشاهده log های CustomerServerFilter
3. بررسی داده‌های ارسالی از server
4. بررسی HTML تولید شده برای جدول
