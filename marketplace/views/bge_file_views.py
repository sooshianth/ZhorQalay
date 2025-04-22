"""
این ماژول شامل توابع و کلاس‌های مربوط به مدیریت فایل‌های BGE در مارکت‌پلیس می‌باشد.
این ماژول امکان آپلود، دانلود، مشاهده و حذف فایل‌های BGE را فراهم می‌کند.
"""

import os
import json
from django.http import JsonResponse, HttpResponse, Http404
from django.conf import settings
import pandas as pd
from django.shortcuts import get_object_or_404
from ..models import BGEFile, BGEProcess
import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from ..serializers import BGEFileSerializer

logger = logging.getLogger(__name__)


def get_bge_file_detail(request, file_id):
    """
    دریافت و نمایش جزئیات یک فایل BGE
    
    این تابع اطلاعات جزئی یک فایل BGE و آخرین وضعیت پردازش آن را برمی‌گرداند.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. دریافت آخرین وضعیت پردازش فایل (در صورت وجود)
    3. تهیه پاسخ JSON با جزئیات فایل و وضعیت پردازش
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل BGE
    خروجی:
        پاسخ JSON شامل اطلاعات فایل و آخرین وضعیت پردازش
    """
    # دریافت فایل با ID مشخص شده یا نمایش خطای 404
    bge_file = get_object_or_404(BGEFile, id=file_id)
    
    # دریافت آخرین وضعیت پردازش (در صورت وجود)
    last_process = BGEProcess.objects.filter(
        bge_file=bge_file
    ).order_by('-id').first()
    
    # تهیه پاسخ با جزئیات فایل
    response_data = {
        'id': bge_file.id,
        'file_name': bge_file.file_name,
        'original_file_name': bge_file.original_file_name,
        'file_path': bge_file.file_path,
        'status': bge_file.status,
        'created_at': bge_file.created_at,
        'process': {
            'id': last_process.id if last_process else None,
            'status': last_process.status if last_process else None,
            'created_at': last_process.created_at if last_process else None,
        } if last_process else None
    }
    
    return JsonResponse(response_data)


def download_bge_file(request, file_id):
    """
    دانلود فایل BGE
    
    این تابع امکان دانلود یک فایل BGE را بر اساس شناسه آن فراهم می‌کند.
    
    فرآیند:
    1. یافتن فایل با شناسه مشخص شده
    2. خواندن محتوای فایل از سیستم فایل
    3. ارسال محتوا به کاربر به عنوان یک فایل دانلودی
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل
    
    خروجی:
        پاسخ HTTP شامل محتوای فایل برای دانلود یا پیام خطا
    """
    try:
        # یافتن فایل با شناسه مشخص شده
        try:
            bge_file = BGEFile.objects.get(id=file_id)
        except BGEFile.DoesNotExist:
            raise Http404(f"فایل با شناسه {file_id} یافت نشد")
        
        # دریافت مسیر فایل در سیستم فایل
        file_path = os.path.join(settings.MEDIA_ROOT, str(bge_file.file))
        if not os.path.exists(file_path):
            logger.error(f"فایل فیزیکی در مسیر {file_path} یافت نشد")
            raise Http404("فایل درخواستی در سرور یافت نشد")
        
        # خواندن محتوای فایل
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        # استخراج نام اصلی فایل
        filename = os.path.basename(str(bge_file.file))
        
        # ثبت رویداد دانلود در سیستم لاگ
        logger.info(f"فایل {filename} توسط کاربر {request.user.username} دانلود شد")
        
        # تنظیم هدرهای پاسخ برای دانلود فایل
        response = HttpResponse(
            file_content,
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # برگرداندن پاسخ دانلود
        return response
        
    except Http404 as e:
        logger.warning(f"درخواست دانلود فایل ناموفق: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"خطا در دانلود فایل BGE با شناسه {file_id}: {str(e)}")
        return HttpResponse(
            f"خطا در دانلود فایل: {str(e)}",
            status=500
        )


def get_bge_file_stats(request, file_id):
    """
    استخراج آمار از فایل BGE
    
    این تابع آمار و اطلاعات آماری از فایل اکسل BGE را استخراج می‌کند، شامل تعداد کل سطرها، 
    آمار مربوط به استان‌ها و وضعیت مشتریان.
    
    فرآیند:
    1. دریافت فایل با شناسه مشخص شده
    2. بارگذاری فایل اکسل با استفاده از pandas
    3. پردازش داده‌ها و استخراج آمار مورد نیاز
    4. تهیه پاسخ JSON با آمار استخراج شده
    
    ورودی:
        request: درخواست HTTP
        file_id: شناسه فایل BGE
    خروجی:
        پاسخ JSON شامل آمار استخراج شده از فایل
    """
    try:
        # دریافت فایل با ID مشخص شده یا نمایش خطای 404
        bge_file = get_object_or_404(BGEFile, id=file_id)
        
        # مسیر کامل فایل در سیستم
        file_path = os.path.join(settings.MEDIA_ROOT, bge_file.file_path)
        
        # بررسی وجود فایل
        if not os.path.exists(file_path):
            logger.error(f"فایل در مسیر {file_path} یافت نشد")
            raise Http404("فایل مورد نظر یافت نشد")
        
        # خواندن فایل اکسل با استفاده از pandas
        df = pd.read_excel(file_path)
        
        # استخراج آمار کلی
        total_rows = len(df)
        
        # آمار بر اساس استان (اگر ستون 'استان' وجود داشته باشد)
        province_stats = {}
        if 'استان' in df.columns:
            province_counts = df['استان'].value_counts().to_dict()
            for province, count in province_counts.items():
                province_stats[province] = count
        
        # آمار بر اساس وضعیت مشتری (اگر ستون 'وضعیت' وجود داشته باشد)
        customer_status_stats = {}
        if 'وضعیت' in df.columns:
            status_counts = df['وضعیت'].value_counts().to_dict()
            for status, count in status_counts.items():
                customer_status_stats[status] = count
        
        # تهیه پاسخ با آمار استخراج شده
        response_data = {
            'total_rows': total_rows,
            'province_stats': province_stats,
            'customer_status_stats': customer_status_stats
        }
        
        return JsonResponse({
            'status': 'success',
            'stats': response_data
        })
        
    except Exception as e:
        # لاگ خطا در صورت بروز مشکل
        logger.error(f"خطا در استخراج آمار فایل با ID {file_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در استخراج آمار: {str(e)}'
        }, status=500)


class BGEFileListView(APIView):
    """
    کلاس مدیریت لیست فایل‌های BGE
    
    این کلاس امکان دریافت لیست فایل‌های BGE و آپلود فایل جدید را فراهم می‌کند.
    """
    parser_classes = (MultiPartParser, FormParser)
    
    def get(self, request):
        """
        دریافت لیست فایل‌های BGE
        
        این متد لیست تمام فایل‌های BGE را با امکان فیلتر کردن برمی‌گرداند.
        
        فرآیند:
        1. دریافت و بررسی پارامترهای فیلتر از درخواست
        2. اعمال فیلترها روی مجموعه فایل‌ها
        3. سریال‌سازی و برگرداندن نتایج
        
        ورودی:
            request: درخواست HTTP که می‌تواند شامل پارامترهای فیلتر باشد:
                - filename: نام فایل (جستجوی فازی)
                - file_type: نوع فایل
                - uploaded_by: کاربر آپلود کننده
        
        خروجی:
            پاسخ JSON شامل لیست فایل‌های BGE فیلتر شده
        """
        try:
            # دریافت تمام فایل‌های BGE
            bge_files = BGEFile.objects.all()
            
            # فیلتر بر اساس پارامترهای موجود در درخواست
            filename = request.query_params.get('filename')
            if filename:
                bge_files = bge_files.filter(file__icontains=filename)
            
            file_type = request.query_params.get('file_type')
            if file_type:
                bge_files = bge_files.filter(file_type=file_type)
            
            uploaded_by = request.query_params.get('uploaded_by')
            if uploaded_by:
                bge_files = bge_files.filter(uploaded_by=uploaded_by)
            
            # سریال‌سازی و برگرداندن نتایج
            serializer = BGEFileSerializer(bge_files, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"خطا در دریافت لیست فایل‌های BGE: {str(e)}")
            return Response(
                {"error": f"خطا در دریافت لیست فایل‌های BGE: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        آپلود فایل BGE جدید
        
        این متد یک فایل BGE جدید را آپلود می‌کند.
        
        فرآیند:
        1. دریافت و اعتبارسنجی فایل آپلود شده
        2. ذخیره فایل در سیستم فایل
        3. ثبت اطلاعات فایل در پایگاه داده
        
        ورودی:
            request: درخواست HTTP شامل فایل آپلود شده و اطلاعات مربوطه:
                - file: فایل آپلود شده
                - file_type: نوع فایل
                - description: توضیحات فایل (اختیاری)
        
        خروجی:
            پاسخ JSON شامل اطلاعات فایل آپلود شده یا پیام خطا
        """
        try:
            # دریافت فایل و داده‌های همراه آن
            file_obj = request.FILES.get('file')
            if not file_obj:
                return Response(
                    {"error": "هیچ فایلی برای آپلود ارسال نشده است"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # بررسی حجم فایل
            if file_obj.size > 20 * 1024 * 1024:  # محدودیت 20 مگابایت
                return Response(
                    {"error": "حجم فایل نمی‌تواند بیشتر از 20 مگابایت باشد"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # سریال‌سازی و اعتبارسنجی داده‌ها
            serializer = BGEFileSerializer(data=request.data)
            if serializer.is_valid():
                # ذخیره اطلاعات فایل
                bge_file = serializer.save(uploaded_by=request.user.username)
                
                # برگرداندن اطلاعات فایل آپلود شده
                return Response(
                    BGEFileSerializer(bge_file).data,
                    status=status.HTTP_201_CREATED
                )
            else:
                # برگرداندن خطاهای اعتبارسنجی
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"خطا در آپلود فایل BGE: {str(e)}")
            return Response(
                {"error": f"خطا در آپلود فایل: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BGEFileDetailView(APIView):
    """
    کلاس مدیریت جزئیات فایل BGE
    
    این کلاس امکان مشاهده جزئیات، دانلود و حذف یک فایل BGE خاص را فراهم می‌کند.
    """
    
    def get(self, request, file_id):
        """
        دریافت اطلاعات یک فایل BGE
        
        این متد جزئیات کامل یک فایل BGE را بر اساس شناسه آن برمی‌گرداند.
        
        فرآیند:
        1. یافتن فایل با شناسه مشخص شده
        2. سریال‌سازی و برگرداندن اطلاعات فایل
        
        ورودی:
            request: درخواست HTTP
            file_id: شناسه فایل
        
        خروجی:
            پاسخ JSON شامل اطلاعات کامل فایل BGE یا پیام خطا
        """
        try:
            # یافتن فایل با شناسه مشخص شده
            try:
                bge_file = BGEFile.objects.get(id=file_id)
            except BGEFile.DoesNotExist:
                return Response(
                    {"error": f"فایل با شناسه {file_id} یافت نشد"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # سریال‌سازی و برگرداندن اطلاعات فایل
            serializer = BGEFileSerializer(bge_file)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"خطا در دریافت اطلاعات فایل BGE با شناسه {file_id}: {str(e)}")
            return Response(
                {"error": f"خطا در دریافت اطلاعات فایل: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, file_id):
        """
        حذف یک فایل BGE
        
        این متد یک فایل BGE را بر اساس شناسه آن حذف می‌کند.
        
        فرآیند:
        1. یافتن فایل با شناسه مشخص شده
        2. حذف فایل از سیستم فایل
        3. حذف اطلاعات فایل از پایگاه داده
        4. برگرداندن تأییدیه حذف
        
        ورودی:
            request: درخواست HTTP
            file_id: شناسه فایل
        
        خروجی:
            پاسخ JSON حاوی تأییدیه حذف یا پیام خطا
        """
        try:
            # یافتن فایل با شناسه مشخص شده
            try:
                bge_file = BGEFile.objects.get(id=file_id)
            except BGEFile.DoesNotExist:
                return Response(
                    {"error": f"فایل با شناسه {file_id} یافت نشد"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # حذف فایل فیزیکی از دیسک
            file_path = os.path.join(settings.MEDIA_ROOT, str(bge_file.file))
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # ذخیره نام فایل قبل از حذف
            filename = os.path.basename(str(bge_file.file))
            
            # حذف رکورد فایل از پایگاه داده
            bge_file.delete()
            
            # برگرداندن تأییدیه حذف
            return Response({
                "message": f"فایل '{filename}' با موفقیت حذف شد"
            })
            
        except Exception as e:
            logger.error(f"خطا در حذف فایل BGE با شناسه {file_id}: {str(e)}")
            return Response(
                {"error": f"خطا در حذف فایل: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def validate_bge_file(file_obj):
    """
    اعتبارسنجی فایل BGE
    
    این تابع یک فایل آپلود شده را از نظر نوع، اندازه و محتوا بررسی می‌کند.
    
    فرآیند:
    1. بررسی پسوند و نوع MIME فایل
    2. بررسی اندازه فایل
    3. بررسی ساختار و محتوای فایل (در صورت نیاز)
    
    ورودی:
        file_obj: شیء فایل آپلود شده
    
    خروجی:
        tuple شامل (is_valid, error_message):
            - is_valid: یک مقدار بولین که نشان می‌دهد آیا فایل معتبر است یا خیر
            - error_message: پیام خطا در صورت نامعتبر بودن فایل (None در صورت معتبر بودن)
    """
    try:
        # بررسی وجود فایل
        if not file_obj:
            return False, "هیچ فایلی ارسال نشده است"
        
        # بررسی پسوند فایل
        filename = file_obj.name
        _, extension = os.path.splitext(filename)
        valid_extensions = ['.pdf', '.xlsx', '.csv', '.xml', '.json']
        
        if extension.lower() not in valid_extensions:
            return False, f"پسوند فایل نامعتبر است. پسوندهای مجاز: {', '.join(valid_extensions)}"
        
        # بررسی اندازه فایل (محدودیت 20 مگابایت)
        max_size = 20 * 1024 * 1024  # 20 MB in bytes
        if file_obj.size > max_size:
            return False, f"حجم فایل بیشتر از حد مجاز است (حداکثر 20 مگابایت)"
        
        # بررسی‌های تخصصی بر اساس نوع فایل
        if extension.lower() == '.pdf':
            # بررسی تخصصی فایل PDF (در صورت نیاز)
            pass
        elif extension.lower() == '.xlsx' or extension.lower() == '.csv':
            # بررسی تخصصی فایل اکسل یا CSV (در صورت نیاز)
            pass
        
        # فایل معتبر است
        return True, None
        
    except Exception as e:
        logger.error(f"خطا در اعتبارسنجی فایل BGE: {str(e)}")
        return False, f"خطا در اعتبارسنجی فایل: {str(e)}" 