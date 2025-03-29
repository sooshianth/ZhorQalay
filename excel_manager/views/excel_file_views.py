import os
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from io import BytesIO
from ..models import ExcelFile, ExcelProcessingLog


@login_required
def excel_files_list(request):
    """
    نمایش لیست فایل‌های اکسل
    """
    excel_files = ExcelFile.objects.filter(file_type__in=['customer', 'purchase', 'other']).order_by('-created_at')
    
    context = {
        'excel_files': excel_files,
        'page_title': 'لیست فایل‌های اکسل',
    }
    return render(request, 'excel_manager/excel_files_list.html', context)


@login_required
def excel_file_detail(request, file_id):
    """
    نمایش جزئیات فایل اکسل
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    processing_logs = excel_file.processing_logs.all().order_by('-processed_at')
    
    # اطلاعات پایه فایل
    file_path = excel_file.file.path
    file_size = os.path.getsize(file_path) / 1024  # کیلوبایت
    
    context = {
        'excel_file': excel_file,
        'processing_logs': processing_logs,
        'file_size': f"{file_size:.2f} KB",
        'page_title': f'جزئیات فایل {excel_file.title}',
    }
    return render(request, 'excel_manager/excel_file_detail.html', context)


@login_required
def upload_excel_file(request):
    """
    آپلود فایل اکسل جدید
    """
    if request.method == 'POST':
        title = request.POST.get('title')
        file_type = request.POST.get('file_type')
        description = request.POST.get('description')
        excel_file = request.FILES.get('excel_file')
        
        if not title or not excel_file or not file_type:
            return JsonResponse({
                'status': 'error',
                'message': 'لطفاً تمام فیلدهای ضروری را پر کنید'
            }, status=400)
        
        # بررسی پسوند فایل
        file_extension = os.path.splitext(excel_file.name)[1].lower()
        if file_extension not in ['.xlsx', '.xls']:
            return JsonResponse({
                'status': 'error',
                'message': 'فقط فایل‌های اکسل (.xlsx, .xls) مجاز هستند'
            }, status=400)
        
        try:
            # ذخیره فایل
            excel_file_obj = ExcelFile.objects.create(
                user=request.user,
                title=title,
                file=excel_file,
                file_type=file_type,
                description=description
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'فایل اکسل با موفقیت آپلود شد',
                'file_id': excel_file_obj.id
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در آپلود فایل: {str(e)}'
            }, status=500)
    
    context = {
        'page_title': 'آپلود فایل اکسل',
    }
    return render(request, 'excel_manager/upload_excel_file.html', context)


@login_required
def preview_excel_file(request, file_id):
    """
    پیش‌نمایش محتوای فایل اکسل
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    try:
        df = pd.read_excel(excel_file.file.path)
        preview_rows = int(request.GET.get('rows', 10))
        preview_rows = min(preview_rows, len(df))
        df_preview = df.head(preview_rows)
        
        table_html = df_preview.to_html(
            classes=['table', 'table-striped', 'table-bordered', 'table-hover'],
            index=False,
            border=0
        )
        
        total_rows = len(df)
        total_columns = len(df.columns)
        file_size = os.path.getsize(excel_file.file.path) / 1024  # کیلوبایت
        
        context = {
            'excel_file': excel_file,
            'table_html': table_html,
            'total_rows': total_rows,
            'preview_rows': preview_rows,
            'total_columns': total_columns,
            'file_size': f"{file_size:.2f} KB",
            'columns': df.columns.tolist(),
            'page_title': f'پیش‌نمایش فایل {excel_file.title}',
        }
        
        return render(request, 'excel_manager/preview_excel_file.html', context)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در خواندن فایل: {str(e)}'
        }, status=500)


@login_required
def process_excel_file(request, file_id):
    """
    پردازش فایل اکسل
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    if request.method == 'POST':
        try:
            # خواندن فایل اکسل
            file_path = excel_file.file.path
            file_extension = os.path.splitext(file_path)[1].lower()
            engine = 'openpyxl' if file_extension == '.xlsx' else 'xlrd'
            
            df = pd.read_excel(excel_file.file.path, engine=engine)
            
            # متغیرهای ثبت گزارش
            records_processed = len(df)
            records_updated = 0
            records_failed = 0
            success = True
            log_messages = []
            
            # پردازش بر اساس نوع فایل
            try:
                if excel_file.file_type == 'customer':
                    # پردازش فایل مشتریان
                    log_messages.append("پردازش فایل مشتریان")
                    # اینجا کد پردازش مشتریان اضافه می‌شود
                    # ...
                    
                elif excel_file.file_type == 'purchase':
                    # پردازش فایل خریدها
                    log_messages.append("پردازش فایل خریدها")
                    # اینجا کد پردازش خریدها اضافه می‌شود
                    # ...
                    
                else:
                    # سایر انواع فایل
                    log_messages.append("نوع فایل برای پردازش خودکار پشتیبانی نمی‌شود")
            except Exception as process_error:
                log_messages.append(f"خطا در پردازش فایل: {str(process_error)}")
                success = False
                records_failed = records_processed
            
            # ایجاد فایل اکسل پردازش شده
            try:
                output_file_path = os.path.splitext(file_path)[0] + "_processed.xlsx"
                df.to_excel(output_file_path, index=False)
                
                # ذخیره فایل پردازش شده
                with open(output_file_path, 'rb') as f:
                    file_content = f.read()
                    file_name = os.path.basename(excel_file.file.name).replace(".xlsx", "_processed.xlsx").replace(".xls", "_processed.xlsx")
                    excel_file.file.save(file_name, ContentFile(file_content), save=False)
                
                # بروزرسانی وضعیت فایل
                excel_file.is_processed = True
                excel_file.save()
            except Exception as save_error:
                log_messages.append(f"خطا در ذخیره فایل پردازش شده: {str(save_error)}")
                success = False
            
            # ثبت گزارش پردازش
            log_message = "\n".join(log_messages)
            ExcelProcessingLog.objects.create(
                excel_file=excel_file,
                processed_by=request.user,
                success=success,
                records_processed=records_processed,
                records_updated=records_updated,
                records_failed=records_failed,
                log_message=log_message
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'فایل اکسل با موفقیت پردازش شد',
                'records_processed': records_processed,
                'records_updated': records_updated,
                'records_failed': records_failed
            })
            
        except Exception as e:
            # ثبت خطا در گزارش
            ExcelProcessingLog.objects.create(
                excel_file=excel_file,
                processed_by=request.user,
                success=False,
                records_processed=0,
                records_updated=0,
                records_failed=0,
                log_message=f"خطا در پردازش فایل: {str(e)}"
            )
            
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در پردازش فایل: {str(e)}'
            }, status=500)
    
    context = {
        'excel_file': excel_file,
        'page_title': f'پردازش فایل {excel_file.title}',
    }
    return render(request, 'excel_manager/preview_excel_file.html', context)


@login_required
def approve_excel_file(request, file_id):
    """
    تأیید فایل اکسل
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    if request.method == 'POST':
        excel_file.is_approved = True
        excel_file.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'فایل اکسل با موفقیت تأیید شد'
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'درخواست نامعتبر'
    }, status=400)


@login_required
def download_excel_file(request, file_id):
    """
    دانلود فایل اکسل
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    try:
        file_path = excel_file.file.path
        with open(file_path, 'rb') as f:
            response = HttpResponse(
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(excel_file.file.name)}"'
            return response
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دانلود فایل: {str(e)}'
        }, status=500)


@login_required
def delete_excel_file(request, file_id):
    """
    حذف فایل اکسل
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    if request.method == 'POST':
        try:
            # حذف فایل فیزیکی
            if os.path.exists(excel_file.file.path):
                os.remove(excel_file.file.path)
            
            # حذف رکورد از دیتابیس
            excel_file.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': 'فایل اکسل با موفقیت حذف شد'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در حذف فایل: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'درخواست نامعتبر'
    }, status=400) 