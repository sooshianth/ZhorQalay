"""
این ماژول شامل توابع مدیریت و رابط کاربری برای فایل‌های اکسل است.
عملکردهای اصلی شامل آپلود، لیست کردن، دانلود و حذف فایل‌های اکسل می‌باشد.
"""

import os
from django.http import HttpResponse, JsonResponse, Http404
from django.conf import settings
import pandas as pd
from ..models import ExcelFile, ExcelProcessingLog, ExcelFile
import logging
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
from core._models import Customer
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class UploadExcelFileView(View):
    """
    نمای آپلود فایل اکسل
    
    این کلاس رابط API برای آپلود فایل‌های اکسل را فراهم می‌کند.
    
    متدها:
        post: دریافت و ذخیره فایل اکسل آپلود شده توسط کاربر
    """
    
    def post(self, request):
        """
        متد پاسخ به درخواست POST برای آپلود فایل
        
        این متد فایل اکسل آپلود شده را دریافت، اعتبارسنجی و در سیستم ذخیره می‌کند.
        
        فرآیند:
        1. دریافت فایل از درخواست
        2. اعتبارسنجی فایل (فرمت و اندازه)
        3. ذخیره فایل در سرور
        4. ایجاد رکورد در پایگاه داده
        
        ورودی:
            request: درخواست HTTP با فایل پیوست شده
        خروجی:
            پاسخ JSON با اطلاعات فایل ذخیره شده یا پیام خطا
        """
        try:
            # دریافت فایل از درخواست
            file = request.FILES['file']
            
            # اعتبارسنجی فایل
            if not file.name.endswith('.xlsx'):
                return JsonResponse({
                    'status': 'error',
                    'message': 'فایل باید با فرمت xlsx باشد'
                }, status=400)
            
            # مسیر ذخیره‌سازی فایل
            current_date = timezone.now().strftime('%Y%m%d')
            upload_folder = os.path.join('excel_files', current_date)
            if not os.path.exists(os.path.join(settings.MEDIA_ROOT, upload_folder)):
                os.makedirs(os.path.join(settings.MEDIA_ROOT, upload_folder))
            
            # ایجاد نام یکتا برای فایل
            file_name = f"{timezone.now().strftime('%Y%m%d%H%M%S')}-{file.name}"
            file_path = os.path.join(upload_folder, file_name)
            file_full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            # ذخیره فایل
            with open(file_full_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # خواندن اطلاعات فایل اکسل
            try:
                df = pd.read_excel(file_full_path)
                num_rows = len(df)
            except Exception as e:
                # حذف فایل در صورت خطا
                if os.path.exists(file_full_path):
                    os.remove(file_full_path)
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در خواندن فایل اکسل: {str(e)}'
                }, status=400)
            
            # ایجاد رکورد فایل در پایگاه داده
            excel_file = ExcelFile.objects.create(
                file_name=file_name,
                original_file_name=file.name,
                file_path=file_path,
                num_rows=num_rows,
                status='pending'
            )
            
            # پاسخ موفق
            return JsonResponse({
                'status': 'success',
                'message': 'فایل با موفقیت آپلود شد',
                'file_id': excel_file.id,
                'file_name': excel_file.original_file_name,
                'num_rows': excel_file.num_rows
            })
            
        except KeyError:
            # خطا: فایل در درخواست وجود ندارد
            return JsonResponse({
                'status': 'error',
                'message': 'فایل برای آپلود یافت نشد'
            }, status=400)
            
        except Exception as e:
            # خطای کلی
            logger.error(f"خطا در آپلود فایل: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در آپلود فایل: {str(e)}'
            }, status=500)

def get_excel_file_detail(request, file_id):
    """
    دریافت و نمایش جزئیات یک فایل اکسل
    
    این تابع اطلاعات جزئی یک فایل اکسل را به همراه آخرین وضعیت پردازش آن برمی‌گرداند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. دریافت آخرین پردازش مربوط به فایل
    3. تهیه پاسخ به صورت JSON با جزئیات فایل و پردازش
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل اکسل
    خروجی:
        پاسخ JSON شامل اطلاعات فایل و پردازش
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    # دریافت آخرین پردازش مرتبط با این فایل
    last_process = ExcelProcessingLog.objects.filter(
        excel_file=excel_file
    ).order_by('-id').first()
    
    # تهیه پاسخ با جزئیات فایل و پردازش
    response_data = {
        'id': excel_file.id,
        'file_name': excel_file.file_name,
        'original_file_name': excel_file.original_file_name,
        'file_path': excel_file.file_path,
        'num_rows': excel_file.num_rows,
        'status': excel_file.status,
        'created_at': excel_file.created_at,
        'process': {
            'id': last_process.id if last_process else None,
            'status': last_process.status if last_process else None,
            'created_at': last_process.created_at if last_process else None,
            'customers_count': last_process.customers_count if last_process else 0,
            'processed_count': last_process.processed_count if last_process else 0,
        } if last_process else None
    }
    
    return JsonResponse(response_data)

def download_excel_file(request, file_id):
    """
    دانلود فایل اکسل
    
    این تابع امکان دانلود فایل اصلی اکسل را با نام اصلی آن فراهم می‌کند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. بررسی وجود فایل فیزیکی در مسیر ذخیره‌سازی
    3. ارسال فایل به عنوان پاسخ HTTP برای دانلود
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل اکسل
    خروجی:
        فایل برای دانلود یا خطای 404
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    # مسیر کامل فایل در سیستم
    file_path = os.path.join(settings.MEDIA_ROOT, excel_file.file_path)
    
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
        response['Content-Disposition'] = f'attachment; filename="{excel_file.original_file_name}"'
        
        return response

def list_excel_files(request):
    """
    نمایش لیست فایل‌های اکسل
    
    این تابع لیست تمام فایل‌های اکسل را با جزئیات آن‌ها برمی‌گرداند.
    امکان فیلتر کردن بر اساس پارامترهای درخواست نیز وجود دارد.
    
    فرآیند:
    1. دریافت پارامترهای فیلتر از درخواست
    2. اعمال فیلترها بر روی کوئری دریافت فایل‌ها
    3. تهیه لیست فایل‌ها با جزئیات
    
    ورودی:
        request: درخواست HTTP با احتمال وجود پارامترهای فیلتر
    خروجی:
        پاسخ JSON شامل لیست فایل‌ها
    """
    # دریافت پارامترهای فیلتر
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    status = request.GET.get('status')
    
    # شروع کوئری پایه
    files = ExcelFile.objects.all().order_by('-created_at')
    
    # اعمال فیلترها
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            # تنظیم به ساعت 00:00 در روز شروع
            files = files.filter(created_at__gte=start_datetime)
        except:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            # تنظیم به ساعت 23:59:59 در روز پایان
            end_datetime = end_datetime + timedelta(days=1, microseconds=-1)
            files = files.filter(created_at__lte=end_datetime)
        except:
            pass
    
    if status:
        files = files.filter(status=status)
    
    # تهیه لیست با جزئیات هر فایل
    result = []
    for file in files:
        # یافتن آخرین پردازش فایل
        last_process = ExcelProcessingLog.objects.filter(
            excel_file=file
        ).order_by('-id').first()
        
        result.append({
            'id': file.id,
            'file_name': file.original_file_name,
            'num_rows': file.num_rows,
            'status': file.status,
            'created_at': file.created_at,
            'process': {
                'id': last_process.id if last_process else None,
                'status': last_process.status if last_process else None,
                'created_at': last_process.created_at if last_process else None,
                'customers_count': last_process.customers_count if last_process else 0,
                'processed_count': last_process.processed_count if last_process else 0,
            } if last_process else None
        })
    
    return JsonResponse({'files': result})

@method_decorator(csrf_exempt, name='dispatch')
class DeleteExcelFileView(View):
    """
    نمای حذف فایل اکسل
    
    این کلاس رابط API برای حذف فایل‌های اکسل را فراهم می‌کند.
    
    متدها:
        post: دریافت درخواست حذف فایل و پردازش آن
    """
    
    def post(self, request, file_id):
        """
        متد پاسخ به درخواست POST برای حذف فایل
        
        این متد فایل اکسل مشخص شده را از سیستم حذف می‌کند.
        
        فرآیند:
        1. دریافت فایل با شناسه مشخص شده
        2. حذف فایل فیزیکی از سرور
        3. حذف رکورد از پایگاه داده
        
        ورودی:
            request: درخواست HTTP
            file_id: شناسه فایل اکسل برای حذف
        خروجی:
            پاسخ JSON با نتیجه عملیات حذف
        """
        try:
            # دریافت فایل با ID مشخص شده یا نمایش خطای 404
            excel_file = get_object_or_404(ExcelFile, id=file_id)
            
            # مسیر کامل فایل در سیستم
            file_path = os.path.join(settings.MEDIA_ROOT, excel_file.file_path)
            
            # حذف فایل فیزیکی اگر وجود داشته باشد
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"خطا در حذف فایل فیزیکی {file_path}: {str(e)}")
            
            # حذف پردازش‌های مرتبط
            try:
                ExcelProcessingLog.objects.filter(excel_file=excel_file).delete()
            except Exception as e:
                logger.error(f"خطا در حذف پردازش‌های مرتبط با فایل {file_id}: {str(e)}")
            
            # حذف رکورد فایل از پایگاه داده
            file_name = excel_file.original_file_name
            excel_file.delete()
            
            # پاسخ موفق
            return JsonResponse({
                'status': 'success',
                'message': f'فایل {file_name} با موفقیت حذف شد'
            })
            
        except Http404:
            # خطا: فایل یافت نشد
            return JsonResponse({
                'status': 'error',
                'message': 'فایل مورد نظر یافت نشد'
            }, status=404)
            
        except Exception as e:
            # خطای کلی
            logger.error(f"خطا در حذف فایل {file_id}: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در حذف فایل: {str(e)}'
            }, status=500) 