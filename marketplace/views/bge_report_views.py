"""
این ماژول شامل توابع و کلاس‌های مربوط به مدیریت گزارش‌های BGE در مارکت‌پلیس می‌باشد.
توابع این ماژول امکان ایجاد، دریافت و پردازش گزارش‌های BGE را فراهم می‌کنند.
"""

import os
import pandas as pd
from datetime import datetime
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import BGEReport, BGEFile
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
def generate_bge_report(request):
    """
    ایجاد گزارش BGE جدید
    
    این تابع یک گزارش BGE جدید را با استفاده از پارامترهای ارائه شده در درخواست ایجاد می‌کند.
    
    فرآیند:
    1. دریافت و اعتبارسنجی پارامترهای درخواست
    2. ایجاد گزارش جدید با مشخصات داده شده
    3. شروع پردازش گزارش به صورت همزمان (اختیاری)
    4. برگرداندن اطلاعات گزارش ایجاد شده
    
    ورودی:
        request: درخواست HTTP شامل پارامترهای گزارش
            - report_type: نوع گزارش
            - period: دوره زمانی گزارش (روزانه/هفتگی/ماهانه)
            - date_from: تاریخ شروع
            - date_to: تاریخ پایان
            - provinces: لیست استان‌ها (اختیاری)
            - process_now: آیا گزارش فوراً پردازش شود؟ (بولین)
    
    خروجی:
        پاسخ JSON شامل شناسه و اطلاعات گزارش ایجاد شده یا پیام خطا
    """
    try:
        # دریافت پارامترهای درخواست
        report_type = request.data.get('report_type')
        period = request.data.get('period')
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        provinces = request.data.get('provinces', [])
        process_now = request.data.get('process_now', False)
        
        # اعتبارسنجی پارامترهای اصلی
        if not all([report_type, period, date_from, date_to]):
            return Response(
                {"error": "تمام پارامترهای ضروری را وارد کنید"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # تبدیل تاریخ‌ها از رشته به شیء تاریخ
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        except ValueError:
            return Response(
                {"error": "فرمت تاریخ نامعتبر است. لطفا از فرمت YYYY-MM-DD استفاده کنید"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ایجاد گزارش جدید
        report = BGEReport.objects.create(
            report_type=report_type,
            period=period,
            date_from=date_from_obj,
            date_to=date_to_obj,
            provinces=provinces,
            status='PENDING'
        )
        
        # اگر پردازش فوری درخواست شده باشد
        if process_now:
            # شروع پردازش گزارش به صورت همزمان
            # (در یک پروژه واقعی، این بخش می‌تواند از سیستم صف مانند Celery استفاده کند)
            report.status = 'PROCESSING'
            report.save()
            
            # اینجا می‌توان تابعی برای پردازش غیرهمزمان گزارش فراخوانی کرد
            # process_report_async.delay(report.id)
        
        # برگرداندن اطلاعات گزارش ایجاد شده
        return Response({
            'report_id': report.id,
            'status': report.status,
            'message': 'گزارش با موفقیت ایجاد شد'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"خطا در ایجاد گزارش BGE: {str(e)}")
        return Response(
            {"error": f"خطا در ایجاد گزارش: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_bge_report(request, report_id):
    """
    دریافت اطلاعات یک گزارش BGE
    
    این تابع جزئیات یک گزارش BGE را بر اساس شناسه آن برمی‌گرداند،
    شامل وضعیت پردازش، تاریخ ایجاد و سایر اطلاعات مربوط به گزارش.
    
    فرآیند:
    1. یافتن گزارش با شناسه مشخص شده
    2. استخراج جزئیات گزارش
    3. برگرداندن اطلاعات گزارش به صورت JSON
    
    ورودی:
        request: درخواست HTTP
        report_id: شناسه گزارش
    
    خروجی:
        پاسخ JSON شامل اطلاعات کامل گزارش یا پیام خطا
    """
    try:
        # یافتن گزارش با شناسه مشخص شده
        try:
            report = BGEReport.objects.get(id=report_id)
        except BGEReport.DoesNotExist:
            return Response(
                {"error": f"گزارش با شناسه {report_id} یافت نشد"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # استخراج اطلاعات گزارش
        report_data = {
            'id': report.id,
            'report_type': report.report_type,
            'period': report.period,
            'date_from': report.date_from,
            'date_to': report.date_to,
            'provinces': report.provinces,
            'status': report.status,
            'created_at': report.created_at,
            'completed_at': report.completed_at,
            'download_url': f"/api/reports/bge/{report.id}/download" if report.status == 'COMPLETED' else None
        }
        
        return Response(report_data)
        
    except Exception as e:
        logger.error(f"خطا در دریافت گزارش BGE با شناسه {report_id}: {str(e)}")
        return Response(
            {"error": f"خطا در دریافت اطلاعات گزارش: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def download_bge_report(request, report_id):
    """
    دانلود فایل گزارش BGE
    
    این تابع امکان دانلود فایل گزارش BGE را فراهم می‌کند،
    به شرطی که گزارش کامل شده باشد و فایل آن موجود باشد.
    
    فرآیند:
    1. یافتن گزارش با شناسه مشخص شده
    2. بررسی وضعیت گزارش و موجود بودن فایل
    3. ارائه فایل برای دانلود
    
    ورودی:
        request: درخواست HTTP
        report_id: شناسه گزارش
    
    خروجی:
        فایل گزارش برای دانلود یا پیام خطا
    """
    try:
        # یافتن گزارش با شناسه مشخص شده
        try:
            report = BGEReport.objects.get(id=report_id)
        except BGEReport.DoesNotExist:
            return Response(
                {"error": f"گزارش با شناسه {report_id} یافت نشد"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # بررسی وضعیت گزارش
        if report.status != 'COMPLETED':
            return Response(
                {"error": "این گزارش هنوز کامل نشده است"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # بررسی وجود فایل گزارش
        if not report.file_path or not os.path.exists(report.file_path):
            return Response(
                {"error": "فایل گزارش یافت نشد"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # آماده‌سازی فایل برای دانلود
        file_name = os.path.basename(report.file_path)
        with open(report.file_path, 'rb') as f:
            file_data = f.read()
            
        # تعیین نوع محتوا بر اساس پسوند فایل
        content_type = 'application/vnd.ms-excel'  # پیش‌فرض برای فایل‌های اکسل
        if file_name.endswith('.xlsx'):
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif file_name.endswith('.csv'):
            content_type = 'text/csv'
        elif file_name.endswith('.pdf'):
            content_type = 'application/pdf'
        
        # ایجاد پاسخ HTTP برای دانلود فایل
        response = HttpResponse(file_data, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        
        return response
        
    except Exception as e:
        logger.error(f"خطا در دانلود گزارش BGE با شناسه {report_id}: {str(e)}")
        return Response(
            {"error": f"خطا در دانلود گزارش: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def list_bge_reports(request):
    """
    دریافت لیست گزارش‌های BGE
    
    این تابع لیست تمام گزارش‌های BGE را با امکان فیلتر کردن برمی‌گرداند.
    
    فرآیند:
    1. دریافت و بررسی پارامترهای فیلتر از درخواست
    2. اعمال فیلترها روی مجموعه گزارش‌ها
    3. مرتب‌سازی نتایج (معمولاً بر اساس تاریخ ایجاد)
    4. برگرداندن لیست گزارش‌ها به صورت JSON
    
    ورودی:
        request: درخواست HTTP که می‌تواند شامل پارامترهای فیلتر باشد:
            - report_type: نوع گزارش
            - status: وضعیت گزارش
            - from_date: تاریخ شروع فیلتر
            - to_date: تاریخ پایان فیلتر
    
    خروجی:
        پاسخ JSON شامل لیست گزارش‌های فیلتر شده
    """
    try:
        # دریافت تمام گزارش‌ها
        reports = BGEReport.objects.all()
        
        # فیلتر بر اساس پارامترهای موجود در درخواست
        report_type = request.query_params.get('report_type')
        if report_type:
            reports = reports.filter(report_type=report_type)
            
        status_param = request.query_params.get('status')
        if status_param:
            reports = reports.filter(status=status_param)
            
        from_date = request.query_params.get('from_date')
        if from_date:
            try:
                from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
                reports = reports.filter(created_at__gte=from_date_obj)
            except ValueError:
                return Response(
                    {"error": "فرمت تاریخ شروع نامعتبر است. لطفا از فرمت YYYY-MM-DD استفاده کنید"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        to_date = request.query_params.get('to_date')
        if to_date:
            try:
                to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
                reports = reports.filter(created_at__lte=to_date_obj)
            except ValueError:
                return Response(
                    {"error": "فرمت تاریخ پایان نامعتبر است. لطفا از فرمت YYYY-MM-DD استفاده کنید"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # مرتب‌سازی گزارش‌ها (جدیدترین اول)
        reports = reports.order_by('-created_at')
        
        # آماده‌سازی داده‌های پاسخ
        report_list = []
        for report in reports:
            report_list.append({
                'id': report.id,
                'report_type': report.report_type,
                'period': report.period,
                'date_from': report.date_from,
                'date_to': report.date_to,
                'status': report.status,
                'created_at': report.created_at,
                'completed_at': report.completed_at
            })
        
        return Response(report_list)
        
    except Exception as e:
        logger.error(f"خطا در دریافت لیست گزارش‌های BGE: {str(e)}")
        return Response(
            {"error": f"خطا در دریافت لیست گزارش‌ها: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def process_bge_report(request, report_id):
    """
    شروع پردازش یک گزارش BGE
    
    این تابع پردازش یک گزارش BGE را شروع می‌کند و برای تولید گزارش،
    داده‌های BGE موجود را پردازش می‌کند.
    
    فرآیند:
    1. یافتن گزارش با شناسه مشخص شده
    2. بررسی وضعیت فعلی گزارش
    3. شروع پردازش گزارش
    4. بروزرسانی وضعیت گزارش
    
    ورودی:
        request: درخواست HTTP
        report_id: شناسه گزارش
    
    خروجی:
        پاسخ JSON شامل نتیجه شروع پردازش یا پیام خطا
    """
    try:
        # یافتن گزارش با شناسه مشخص شده
        try:
            report = BGEReport.objects.get(id=report_id)
        except BGEReport.DoesNotExist:
            return Response(
                {"error": f"گزارش با شناسه {report_id} یافت نشد"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # بررسی وضعیت فعلی گزارش
        if report.status == 'PROCESSING':
            return Response(
                {"error": "این گزارش در حال حاضر در حال پردازش است"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if report.status == 'COMPLETED':
            return Response(
                {"error": "این گزارش قبلاً کامل شده است"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # بروزرسانی وضعیت گزارش به 'در حال پردازش'
        report.status = 'PROCESSING'
        report.save()
        
        # در یک پروژه واقعی، پردازش گزارش باید به صورت غیرهمزمان انجام شود
        # به عنوان مثال با استفاده از Celery:
        # process_report_task.delay(report_id)
        
        # اینجا می‌توان به صورت ساده پردازش را شبیه‌سازی کرد
        # (در پروژه واقعی این کد باید در یک تسک غیرهمزمان اجرا شود)
        try:
            # استخراج داده‌های BGE مرتبط با بازه زمانی گزارش
            bge_files = BGEFile.objects.filter(
                upload_date__gte=report.date_from,
                upload_date__lte=report.date_to
            )
            
            if not bge_files.exists():
                report.status = 'FAILED'
                report.error_message = 'هیچ فایل BGE برای بازه زمانی مشخص شده یافت نشد'
                report.save()
                return Response({
                    'status': 'FAILED',
                    'message': 'هیچ فایل BGE برای بازه زمانی مشخص شده یافت نشد'
                })
            
            # در اینجا باید منطق واقعی پردازش گزارش اجرا شود
            # ...
            
            # پس از اتمام پردازش، بروزرسانی وضعیت گزارش
            report.status = 'COMPLETED'
            report.completed_at = datetime.now()
            report.file_path = '/path/to/report.xlsx'  # فایل گزارش تولید شده
            report.save()
            
        except Exception as processing_error:
            report.status = 'FAILED'
            report.error_message = str(processing_error)
            report.save()
            logger.error(f"خطا در پردازش گزارش {report_id}: {str(processing_error)}")
            
        return Response({
            'report_id': report_id,
            'status': report.status,
            'message': 'درخواست پردازش گزارش با موفقیت ثبت شد'
        })
        
    except Exception as e:
        logger.error(f"خطا در شروع پردازش گزارش BGE با شناسه {report_id}: {str(e)}")
        return Response(
            {"error": f"خطا در پردازش گزارش: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def cancel_bge_report(request, report_id):
    """
    لغو پردازش یک گزارش BGE
    
    این تابع پردازش یک گزارش BGE در حال اجرا را لغو می‌کند.
    
    فرآیند:
    1. یافتن گزارش با شناسه مشخص شده
    2. بررسی وضعیت فعلی گزارش
    3. لغو پردازش گزارش
    4. بروزرسانی وضعیت گزارش
    
    ورودی:
        request: درخواست HTTP
        report_id: شناسه گزارش
    
    خروجی:
        پاسخ JSON شامل نتیجه لغو پردازش یا پیام خطا
    """
    try:
        # یافتن گزارش با شناسه مشخص شده
        try:
            report = BGEReport.objects.get(id=report_id)
        except BGEReport.DoesNotExist:
            return Response(
                {"error": f"گزارش با شناسه {report_id} یافت نشد"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # بررسی وضعیت فعلی گزارش
        if report.status != 'PROCESSING' and report.status != 'PENDING':
            return Response(
                {"error": f"لغو پردازش برای گزارش با وضعیت {report.status} امکان‌پذیر نیست"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # در پروژه واقعی، اینجا باید تسک غیرهمزمان مربوطه را لغو کنید
        # به عنوان مثال: revoke(task_id, terminate=True)
        
        # بروزرسانی وضعیت گزارش
        report.status = 'CANCELLED'
        report.save()
        
        return Response({
            'report_id': report_id,
            'status': 'CANCELLED',
            'message': 'پردازش گزارش با موفقیت لغو شد'
        })
        
    except Exception as e:
        logger.error(f"خطا در لغو پردازش گزارش BGE با شناسه {report_id}: {str(e)}")
        return Response(
            {"error": f"خطا در لغو پردازش گزارش: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 