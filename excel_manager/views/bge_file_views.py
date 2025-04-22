# This file is now deprecated. Import functions from new modular views.
# Keeping this file for backward compatibility.

from .bge_file_list_views import (
    bge_files_list,
    view_excel_file,
    search_cargo_products
)

from .bge_file_upload_views import (
    upload_bge_file,
    approve_bge_file
)

from .bge_file_process_views import (
    process_bge_file
)

# Define other imported utilities to maintain compatibility
from .utils import (
    normalize_text,
    extract_province_from_address,
    get_excel_columns,
    fix_excel_headers,
    map_excel_field_to_model
)

"""
این ماژول شامل توابع مدیریت نمایش و دسترسی به فایل‌های اکسل بازارگاه است.
توابع این ماژول مسئول نمایش جزئیات فایل، دانلود فایل و دریافت اطلاعات آماری هستند.
"""

import os
from django.http import HttpResponse, JsonResponse, Http404
from django.conf import settings
import pandas as pd
from ..models import BGEFile, BGEProcess
import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)

def get_bge_file_detail(request, file_id):
    """
    دریافت و نمایش جزئیات یک فایل بازارگاه بر اساس شناسه فایل
    
    این تابع اطلاعات جزئی یک فایل بازارگاه را به همراه آخرین وضعیت پردازش آن برمی‌گرداند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. دریافت آخرین پردازش مربوط به فایل
    3. تهیه پاسخ به صورت JSON با جزئیات فایل و پردازش
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل بازارگاه
    خروجی:
        پاسخ JSON شامل اطلاعات فایل و پردازش
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    bge_file = get_object_or_404(BGEFile, id=file_id)
    
    # دریافت آخرین پردازش مرتبط با این فایل
    last_process = BGEProcess.objects.filter(
        bge_file=bge_file
    ).order_by('-id').first()
    
    # تهیه پاسخ با جزئیات فایل و پردازش
    response_data = {
        'id': bge_file.id,
        'file_name': bge_file.file_name,
        'original_file_name': bge_file.original_file_name,
        'file_path': bge_file.file_path,
        'num_rows': bge_file.num_rows,
        'status': bge_file.status,
        'created_at': bge_file.created_at,
        'process': {
            'id': last_process.id if last_process else None,
            'status': last_process.status if last_process else None,
            'created_at': last_process.created_at if last_process else None,
            'customers_count': last_process.customers_count if last_process else 0,
            'processed_count': last_process.processed_count if last_process else 0,
        } if last_process else None
    }
    
    return JsonResponse(response_data)

def download_bge_file(request, file_id):
    """
    دانلود فایل بازارگاه
    
    این تابع امکان دانلود فایل اصلی بازارگاه را با نام اصلی آن فراهم می‌کند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. بررسی وجود فایل فیزیکی در مسیر ذخیره‌سازی
    3. ارسال فایل به عنوان پاسخ HTTP برای دانلود
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل بازارگاه
    خروجی:
        فایل برای دانلود یا خطای 404
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    bge_file = get_object_or_404(BGEFile, id=file_id)
    
    # مسیر کامل فایل در سیستم
    file_path = os.path.join(settings.MEDIA_ROOT, bge_file.file_path)
    
    # بررسی وجود فایل
    if not os.path.exists(file_path):
        logger.error(f"فایل در مسیر {file_path} یافت نشد")
        raise Http404("فایل مورد نظر یافت نشد")
    
    # باز کردن فایل برای خواندن
    with open(file_path, 'rb') as file:
        # تنظیم هدرهای HTTP برای دانلود
        response = HttpResponse(
            file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        # تنظیم نام فایل برای دانلود بر اساس نام اصلی فایل
        response['Content-Disposition'] = f'attachment; filename="{bge_file.original_file_name}"'
        
        return response

def get_bge_file_stats(request, file_id):
    """
    دریافت آمار و اطلاعات تحلیلی فایل بازارگاه
    
    این تابع اطلاعات آماری از فایل اکسل استخراج می‌کند، از جمله:
    - تعداد سطرها
    - تعداد استان‌ها
    - لیست استان‌ها همراه با تعداد سفارش در هر استان
    - لیست ستون‌های فایل
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. خواندن محتوای فایل اکسل با پاندا
    3. استخراج و تحلیل اطلاعات استان‌ها
    4. تهیه آمار و اطلاعات تحلیلی
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل بازارگاه
    خروجی:
        پاسخ JSON شامل آمار و اطلاعات تحلیلی فایل
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    bge_file = get_object_or_404(BGEFile, id=file_id)
    
    # مسیر کامل فایل در سیستم
    file_path = os.path.join(settings.MEDIA_ROOT, bge_file.file_path)
    
    # بررسی وجود فایل
    if not os.path.exists(file_path):
        logger.error(f"فایل در مسیر {file_path} یافت نشد")
        return JsonResponse({'error': 'فایل مورد نظر یافت نشد'}, status=404)
    
    try:
        # خواندن محتوای فایل - بسته به نوع فایل (HTML یا Excel)
        try:
            # ابتدا سعی کنیم فایل را به عنوان HTML بخوانیم
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '<html' in content.lower():
                # فایل HTML است
                df = pd.read_html(content)[0]
            else:
                # فایل اکسل است
                df = pd.read_excel(file_path)
        except:
            # اگر خواندن به صورت HTML موفق نبود، به عنوان اکسل بخوانیم
            df = pd.read_excel(file_path)
        
        # اصلاح سربرگ‌های فایل در صورت نیاز
        df = fix_excel_headers(df)
        
        # یافتن ستون آدرس در فایل (بسته به ساختار فایل می‌تواند متفاوت باشد)
        address_column = None
        for col in df.columns:
            if 'آدرس' in str(col) or 'استان' in str(col):
                address_column = col
                break
        
        # آماده‌سازی داده‌های آماری
        provinces_data = {}
        
        # اگر ستون آدرس یافت شد، استان‌ها را استخراج و شمارش کنیم
        if address_column:
            for _, row in df.iterrows():
                address = row[address_column] if pd.notna(row[address_column]) else ""
                province = extract_province_from_address(address)
                
                if province:
                    province = normalize_text(province)
                    if province in provinces_data:
                        provinces_data[province] += 1
                    else:
                        provinces_data[province] = 1
        
        # تبدیل دیکشنری استان‌ها به لیست مرتب شده بر اساس تعداد
        provinces_list = [
            {'province': province, 'count': count} 
            for province, count in provinces_data.items()
        ]
        # مرتب‌سازی بر اساس تعداد، نزولی
        provinces_list = sorted(provinces_list, key=lambda x: x['count'], reverse=True)
        
        # تهیه ستون‌های فایل
        columns = df.columns.tolist()
        
        # تهیه پاسخ نهایی با آمار و اطلاعات
        response_data = {
            'file_id': bge_file.id,
            'rows_count': len(df),
            'provinces_count': len(provinces_data),
            'provinces': provinces_list,
            'columns': columns
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # ثبت خطا و برگرداندن پیام خطا
        logger.error(f"خطا در استخراج آمار فایل {file_id}: {str(e)}")
        return JsonResponse({'error': f'خطا در پردازش فایل: {str(e)}'}, status=500)