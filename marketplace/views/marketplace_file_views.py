"""
این ماژول شامل توابع مربوط به مدیریت فایل‌های مارکت‌پلیس می‌باشد.
توابع و کلاس‌های این ماژول امکان آپلود، دانلود، نمایش و حذف فایل‌های مارکت‌پلیس را فراهم می‌کنند.
"""

import os
import uuid
import json
from datetime import datetime
from django.http import JsonResponse, HttpResponse, Http404
from django.views import View
from django.utils.decorators import method_decorator
from django.conf import settings
from django.shortcuts import get_object_or_404
from ..models import MarketplaceFile, MarketplaceFileProcessStatus
from ..utils.auth import token_required
from ..serializers import MarketplaceFileSerializer
import logging

logger = logging.getLogger(__name__)


class UploadMarketplaceFileView(View):
    """
    کلاس نمایشی برای آپلود فایل مارکت‌پلیس
    
    این کلاس امکان دریافت و ذخیره‌سازی فایل‌های مارکت‌پلیس را فراهم می‌کند. فایل‌ها پس از 
    دریافت با نام یکتا ذخیره شده و در پایگاه داده ثبت می‌شوند.
    
    فرآیند:
    1. دریافت فایل از درخواست HTTP
    2. ایجاد نام یکتا برای فایل
    3. ذخیره فایل در مسیر مشخص شده
    4. ثبت اطلاعات فایل در پایگاه داده
    5. برگرداندن اطلاعات فایل ذخیره شده
    """
    
    @method_decorator(token_required)
    def post(self, request, *args, **kwargs):
        """
        پردازش درخواست POST برای آپلود فایل
        
        این متد درخواست آپلود فایل را پردازش کرده و پس از ذخیره‌سازی، اطلاعات آن را برمی‌گرداند.
        
        ورودی:
            request: درخواست HTTP حاوی فایل آپلود شده
            *args, **kwargs: پارامترهای اضافی
        خروجی:
            پاسخ JSON حاوی اطلاعات فایل ذخیره شده یا پیام خطا
        """
        # بررسی وجود فایل در درخواست
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'فایل در درخواست یافت نشد'
            }, status=400)
        
        # دریافت فایل از درخواست
        uploaded_file = request.FILES['file']
        original_filename = uploaded_file.name
        
        # بررسی پسوند فایل
        if not original_filename.endswith(('.xlsx', '.xls')):
            return JsonResponse({
                'status': 'error',
                'message': 'فرمت فایل باید اکسل (.xlsx یا .xls) باشد'
            }, status=400)
        
        # ایجاد نام یکتا برای فایل
        unique_filename = f"{uuid.uuid4()}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        
        # مسیر ذخیره‌سازی فایل
        directory = os.path.join('uploads', 'marketplace_files')
        file_path = os.path.join(directory, unique_filename)
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        # اطمینان از وجود دایرکتوری
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # ذخیره فایل
        with open(full_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # ایجاد رکورد فایل در پایگاه داده
        marketplace_file = MarketplaceFile.objects.create(
            file_name=unique_filename,
            original_file_name=original_filename,
            file_path=file_path,
            user=request.user
        )
        
        # برگرداندن اطلاعات فایل
        return JsonResponse({
            'status': 'success',
            'file': {
                'id': marketplace_file.id,
                'file_name': marketplace_file.file_name,
                'original_file_name': marketplace_file.original_file_name,
                'file_path': marketplace_file.file_path,
                'status': marketplace_file.status,
                'created_at': marketplace_file.created_at,
            }
        })


def get_marketplace_file_detail(request, file_id):
    """
    دریافت و نمایش جزئیات یک فایل مارکت‌پلیس
    
    این تابع اطلاعات جزئی یک فایل مارکت‌پلیس و آخرین وضعیت پردازش آن را برمی‌گرداند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. دریافت آخرین وضعیت پردازش فایل (در صورت وجود)
    3. تهیه پاسخ JSON با جزئیات فایل و وضعیت پردازش
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل مارکت‌پلیس
    خروجی:
        پاسخ JSON شامل اطلاعات فایل و آخرین وضعیت پردازش
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    marketplace_file = get_object_or_404(MarketplaceFile, id=file_id)
    
    # دریافت آخرین وضعیت پردازش (در صورت وجود)
    last_status = MarketplaceFileProcessStatus.objects.filter(
        marketplace_file=marketplace_file
    ).order_by('-created_at').first()
    
    # تهیه پاسخ با جزئیات فایل
    response_data = {
        'id': marketplace_file.id,
        'file_name': marketplace_file.file_name,
        'original_file_name': marketplace_file.original_file_name,
        'file_path': marketplace_file.file_path,
        'status': marketplace_file.status,
        'created_at': marketplace_file.created_at,
        'last_process_status': None
    }
    
    # اضافه کردن اطلاعات آخرین وضعیت پردازش (اگر وجود داشته باشد)
    if last_status:
        response_data['last_process_status'] = {
            'id': last_status.id,
            'status': last_status.status,
            'message': last_status.message,
            'created_at': last_status.created_at
        }
    
    return JsonResponse(response_data)


def download_marketplace_file(request, file_id):
    """
    دانلود فایل مارکت‌پلیس
    
    این تابع امکان دانلود فایل مارکت‌پلیس را با نام اصلی آن فراهم می‌کند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. بررسی وجود فایل فیزیکی در مسیر ذخیره‌سازی
    3. ارسال فایل به عنوان پاسخ HTTP برای دانلود
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل مارکت‌پلیس
    خروجی:
        فایل برای دانلود یا خطای 404
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    marketplace_file = get_object_or_404(MarketplaceFile, id=file_id)
    
    # مسیر کامل فایل در سیستم
    file_path = os.path.join(settings.MEDIA_ROOT, marketplace_file.file_path)
    
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
        response['Content-Disposition'] = f'attachment; filename="{marketplace_file.original_file_name}"'
        
        return response


def list_marketplace_files(request):
    """
    نمایش لیست فایل‌های مارکت‌پلیس
    
    این تابع لیست تمام فایل‌های مارکت‌پلیس را با امکان فیلتر کردن بر اساس وضعیت نمایش می‌دهد.
    
    فرآیند:
    1. دریافت پارامترهای فیلتر از درخواست (مانند وضعیت)
    2. استخراج فایل‌های مطابق با فیلترها
    3. تهیه پاسخ JSON با لیست فایل‌ها
    
    ورودی:
        request: درخواست HTTP با پارامترهای اختیاری برای فیلتر کردن
    خروجی:
        پاسخ JSON شامل لیست فایل‌های مارکت‌پلیس
    """
    # دریافت پارامتر status از query string
    status = request.GET.get('status')
    
    # پایه کوئری
    query = MarketplaceFile.objects.all()
    
    # اعمال فیلتر وضعیت اگر مشخص شده باشد
    if status:
        query = query.filter(status=status)
    
    # مرتب‌سازی بر اساس زمان ایجاد (جدیدترین ابتدا)
    files = query.order_by('-created_at')
    
    # سریال‌سازی داده‌ها
    serialized_files = MarketplaceFileSerializer(files, many=True).data
    
    return JsonResponse({
        'status': 'success',
        'files': serialized_files
    })


class DeleteMarketplaceFileView(View):
    """
    کلاس نمایشی برای حذف فایل مارکت‌پلیس
    
    این کلاس امکان حذف فایل مارکت‌پلیس را فراهم می‌کند. هم فایل فیزیکی و هم
    رکورد مربوط به آن در پایگاه داده حذف می‌شود.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. حذف فایل فیزیکی از سیستم فایل
    3. حذف رکورد فایل از پایگاه داده
    """
    
    @method_decorator(token_required)
    def delete(self, request, file_id, *args, **kwargs):
        """
        پردازش درخواست DELETE برای حذف فایل
        
        این متد درخواست حذف فایل را پردازش کرده و پس از حذف، پیام موفقیت را برمی‌گرداند.
        
        ورودی:
            request: درخواست HTTP
            file_id: شناسه فایل مارکت‌پلیس برای حذف
            *args, **kwargs: پارامترهای اضافی
        خروجی:
            پاسخ JSON با وضعیت عملیات
        """
        try:
            # دریافت فایل با ID مشخص شده یا نمایش خطای 404
            marketplace_file = get_object_or_404(MarketplaceFile, id=file_id)
            
            # مسیر کامل فایل در سیستم
            file_path = os.path.join(settings.MEDIA_ROOT, marketplace_file.file_path)
            
            # حذف فایل فیزیکی (اگر وجود داشته باشد)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"فایل فیزیکی {file_path} با موفقیت حذف شد")
            else:
                logger.warning(f"فایل فیزیکی {file_path} یافت نشد")
            
            # حذف رکورد فایل از پایگاه داده
            marketplace_file.delete()
            logger.info(f"رکورد فایل با ID {file_id} با موفقیت حذف شد")
            
            return JsonResponse({
                'status': 'success',
                'message': 'فایل با موفقیت حذف شد'
            })
            
        except Exception as e:
            # لاگ خطا در صورت بروز مشکل
            logger.error(f"خطا در حذف فایل با ID {file_id}: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در حذف فایل: {str(e)}'
            }, status=500) 