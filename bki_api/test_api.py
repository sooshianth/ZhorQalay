#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import django

# تنظیم محیط جنگو
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kunqalay.settings')
django.setup()

# واردات توابع مورد نیاز
from bki_api.bki_kharid_list_by_date import get_purchases_last_24_hours, get_all_purchases_by_date_range
from bki_api.bki_api_utils import analyze_api_response, process_purchase_data_new
from bki_api.models import BKILog

def test_get_purchases_last_24_hours():
    """
    تست دریافت خریدهای 24 ساعت گذشته از API
    """
    print("=== تست دریافت خریدهای 24 ساعت گذشته ===")
    
    try:
        result = get_purchases_last_24_hours()
        
        if isinstance(result, tuple) and len(result) == 6:
            total, success, created, updated, failed, errors = result
            print(f"نتیجه: کل={total}, موفق={success}, جدید={created}, بروزرسانی={updated}, خطا={failed}")
            
            if errors:
                print("خطاها:")
                for error in errors:
                    print(f"- {error}")
        else:
            print(f"فرمت نتیجه نامعتبر است: {result}")
    
    except Exception as e:
        print(f"خطا در اجرای تابع: {str(e)}")
        import traceback
        print(traceback.format_exc())

def test_get_purchases_by_date_range():
    """
    تست دریافت خریدهای بازه زمانی مشخص
    """
    print("=== تست دریافت خریدهای بازه زمانی مشخص ===")
    
    # تعیین بازه زمانی برای تست
    from_date = "1403/01/01"
    to_date = "1403/01/10"
    
    print(f"دریافت خریدها از {from_date} تا {to_date}")
    
    try:
        result = get_all_purchases_by_date_range(from_date, to_date)
        
        if isinstance(result, tuple) and len(result) == 6:
            total, success, created, updated, failed, errors = result
            print(f"نتیجه: کل={total}, موفق={success}, جدید={created}, بروزرسانی={updated}, خطا={failed}")
            
            if errors:
                print("خطاها:")
                for error in errors:
                    print(f"- {error}")
        else:
            print(f"فرمت نتیجه نامعتبر است: {result}")
    
    except Exception as e:
        print(f"خطا در اجرای تابع: {str(e)}")
        import traceback
        print(traceback.format_exc())

def test_analyze_last_response():
    """
    تحلیل آخرین پاسخ موفق API
    """
    print("=== تحلیل آخرین پاسخ API ===")
    
    try:
        # دریافت آخرین لاگ موفق
        last_log = BKILog.objects.filter(is_successful=True).order_by('-created_at').first()
        
        if not last_log:
            print("هیچ لاگ موفقی یافت نشد")
            return
            
        print(f"لاگ یافت شده: {last_log.id} - {last_log.created_at}")
        print(f"نوع درخواست: {last_log.request_type}")
        
        # تحلیل پاسخ
        analysis = analyze_api_response(last_log.response_data)
        
        print(f"آیا پاسخ معتبر است؟ {analysis['is_valid']}")
        print(f"فرمت پاسخ: {analysis['format']}")
        
        if analysis['error']:
            print(f"خطا: {analysis['error']}")
        
        if analysis['sample_keys']:
            print(f"نمونه کلیدها: {', '.join(analysis['sample_keys'])}")
    
    except Exception as e:
        print(f"خطا در تحلیل پاسخ: {str(e)}")
        import traceback
        print(traceback.format_exc())

def test_process_purchase_data():
    """
    تست پردازش داده‌های خرید با تابع process_purchase_data_new
    """
    print("=== تست پردازش داده‌های خرید ===")
    
    try:
        # داده‌های آزمایشی برای تست
        test_data = {
            'idkharid': '1234567',
            'kutajnumber': '98765',
            'goodtitle': 'ذرت دانه‌ای',
            'qty': '25000',
            'wbarnamehshode': '24000',
            'buyername': 'علی محمدی',
            'buyerphone': '09123456789',
            'fee': '65000',
            'allocationid': 'ALLOC123456,ALLOC789012'
        }
        
        print("داده‌های آزمایشی:")
        for key, value in test_data.items():
            print(f"  {key}: {value}")
        
        # پردازش داده‌ها
        purchase, created, error = process_purchase_data_new(test_data)
        
        if error:
            print(f"خطا در پردازش: {error}")
        else:
            status = "ایجاد شد" if created else "به‌روزرسانی شد"
            print(f"خرید با موفقیت {status}")
            print(f"شماره خرید: {purchase.purchase_number}")
            print(f"مشتری: {purchase.customer.name}")
            print(f"وزن سفارش: {purchase.order_weight}")
            print(f"وزن تحویلی: {purchase.delivered_weight}")
            
            if purchase.extelaf_type:
                print(f"اختلاف: {purchase.extelaf_type} - {purchase.extelaf_weight} کیلوگرم - {purchase.extelaf_amount} ریال")
            
            if purchase.cargo:
                print(f"کوتاژ: {purchase.cargo.cottage} - نوع محصول: {purchase.cargo.get_product_type_display()}")
            
            print(f"وضعیت: {purchase.state}")
            
            # بررسی شناسه‌های تخصیص
            from core.PurchaseModel import ShenaseTakhsis
            allocations = ShenaseTakhsis.objects.filter(purchase=purchase)
            if allocations.exists():
                print("شناسه‌های تخصیص:")
                for allocation in allocations:
                    print(f"  - {allocation.code}")
    
    except Exception as e:
        print(f"خطا در تست: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    # اجرای تست‌ها
    print("=== تست پردازش داده‌های خرید ===")
    test_process_purchase_data()
    
    print("\n=== تست دریافت خریدهای 24 ساعت گذشته ===")
    test_get_purchases_last_24_hours()
    
    print("\n=== تست دریافت خریدهای بازه زمانی مشخص ===")
    test_get_purchases_by_date_range()
    
    print("\n=== تحلیل آخرین پاسخ API ===")
    test_analyze_last_response() 