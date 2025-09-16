from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
import pandas as pd
import numpy as np
import json
import os
import uuid
import tempfile
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.db.models.fields import Field
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from urllib.parse import quote
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import smart_str
import csv
from openpyxl.utils import get_column_letter
import logging
from core.decorators.decorators import role_required


logger = logging.getLogger("data_exflow_views")

from .models import ImportExportSession, ImportExportLog, ImportRecord
from .utils import (
    get_file_extension, is_valid_file_type, read_file_to_dataframe,
    get_all_registered_models, get_model_fields, validate_import_data,
    process_import, revert_import, process_export, check_file_size, get_column_letter
)

# Create your views here.

def get_client_ip(request):
    """
    دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
    """
    if not request:
        return "Unknown"
        
    # IP مستقیم (از سرور دیده می‌شود)
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
    # IP از طریق proxy headers
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')

    # انتخاب IP اصلی
    client_ip = direct_ip
    if forwarded_for:
        # اولین IP در لیست X-Forwarded-For
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
        
    # اگر proxy وجود دارد، هر دو IP را نمایش بده
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
        
    return f"{client_ip}-{proxy_info}"

def validate_content_type(content_type_id):
    """Validate a content type ID for security."""
    try:
        # Try to get the content type
        content_type = ContentType.objects.get(id=content_type_id)
        
        # تلاش برای دریافت کلاس مدل
        model_class = content_type.model_class()
        if model_class is None:
            raise ValidationError(f"مدل {content_type.app_label}.{content_type.model} پیدا نشد")
            
        return content_type
        
    except ContentType.DoesNotExist:
        raise ValidationError("مدل انتخابی نامعتبر است")
    except Exception as e:
        raise ValidationError(f"خطا در اعتبارسنجی مدل: {str(e)}")

@login_required
@role_required('admin','logistics_manager') 
def index_view(request):
    """نمایش داشبورد اصلی"""
    logger.warning(f"Index view called by {get_client_ip(request)}, user: {request.user}")
    # دریافت جلسات اخیر
    recent_sessions = ImportExportSession.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    # محاسبه آمار
    import_count = ImportExportSession.objects.filter(
        user=request.user, 
        session_type='import'
    ).count()
    
    export_count = ImportExportSession.objects.filter(
        user=request.user, 
        session_type='export'
    ).count()
    
    # تعداد مدل‌های قابل استفاده
    model_count = ContentType.objects.filter(
        app_label__in=['core', 'accounts', 'data_exflow']  # اپ‌های مورد نظر
    ).count()
    
    # تعداد کل رکوردهای پردازش شده
    record_count = ImportExportSession.objects.filter(
        user=request.user,
        status='completed'
    ).aggregate(
        total=Count('processed_count')
    )['total'] or 0
    
    # محاسبه نرخ موفقیت
    import_sessions = ImportExportSession.objects.filter(
        user=request.user, 
        session_type='import'
    )
    import_success = import_sessions.filter(status='completed').count()
    import_total = import_sessions.count()
    import_success_rate = (import_success * 100 // import_total) if import_total > 0 else 0
    import_failure_rate = 100 - import_success_rate
    
    export_sessions = ImportExportSession.objects.filter(
        user=request.user, 
        session_type='export'
    )
    export_success = export_sessions.filter(status='completed').count()
    export_total = export_sessions.count()
    export_success_rate = (export_success * 100 // export_total) if export_total > 0 else 0
    export_failure_rate = 100 - export_success_rate
    
    # داده‌های نمودار (6 ماه اخیر)
    six_months_ago = timezone.now() - timedelta(days=180)
    
    # آمار ماهانه ورود داده
    import_monthly = []
    export_monthly = []
    
    for i in range(6):
        month_start = six_months_ago + timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        
        import_count_month = ImportExportSession.objects.filter(
            user=request.user,
            session_type='import',
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()
        
        export_count_month = ImportExportSession.objects.filter(
            user=request.user,
            session_type='export',
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()
        
        import_monthly.append(import_count_month)
        export_monthly.append(export_count_month)
    
    context = {
        'title': 'داشبورد مدیریت داده‌ها',
        'recent_sessions': recent_sessions,
        'import_count': import_count,
        'export_count': export_count,
        'model_count': model_count,
        'record_count': record_count,
        'import_success_rate': import_success_rate,
        'import_failure_rate': import_failure_rate,
        'export_success_rate': export_success_rate,
        'export_failure_rate': export_failure_rate,
        'chart_import_data': ','.join(map(str, import_monthly)),
        'chart_export_data': ','.join(map(str, export_monthly)),
    }
    
    return render(request, 'data_exflow/index.html', context)

# ---------------------------
# Import Views
# ---------------------------

@login_required
@role_required('admin','logistics_manager') 
def import_view(request):
    """Main import view showing available models to import."""
    models = get_all_registered_models()
    
    # تبدیل مدل‌ها به فرمت مناسب ContentType برای نمایش در صفحه
    content_types = []
    for app_label, model_list in models.items():
        for model in model_list:
            if model.get('content_type_id'):
                try:
                    ct = ContentType.objects.get(id=model['content_type_id'])
                    content_types.append({
                        'id': ct.id,
                        'app_label': app_label,
                        'model': ct.model,
                        'model_verbose_name': model['verbose_name']
                    })
                except ContentType.DoesNotExist:
                    # اگر ContentType وجود نداشت، آن را ایجاد می‌کنیم
                    try:
                        model_class = apps.get_model(app_label, model['name'])
                        ct = ContentType.objects.get_for_model(model_class)
                        content_types.append({
                            'id': ct.id,
                            'app_label': app_label,
                            'model': ct.model,
                            'model_verbose_name': model['verbose_name']
                        })
                    except Exception as e:
                        logger.warning(f"خطا در دریافت مدل {app_label}.{model['name']}: {str(e)}")
                        continue
    
    # Get recent import sessions
    recent_imports = ImportExportSession.objects.filter(
        user=request.user,
        session_type=ImportExportSession.IMPORT
    ).order_by('-created_at')[:5]
    
    context = {
        'title': 'ورود داده',
        'models': models,
        'content_types': content_types,
        'import_sessions': recent_imports,
        'standalone': True,
    }
    
    return render(request, 'data_exflow/import.html', context)


@login_required
@role_required('admin','logistics_manager') 
def import_upload(request):
    """Handle file upload for import."""
    if request.method != 'POST':
        return redirect('data_exflow:import')
    
    # Get form data
    content_type_id = request.POST.get('content_type_id')
    file = request.FILES.get('file')
    
    # Validate required fields with specific error messages
    if not content_type_id:
        messages.error(request, 'لطفاً مدل داده را انتخاب کنید')
        return redirect('data_exflow:import')
        
    if not file:
        messages.error(request, 'لطفاً فایل مورد نظر را انتخاب کنید')
        return redirect('data_exflow:import')
    
    # Check if content type exists
    try:
        content_type = validate_content_type(content_type_id)
    except ValidationError as e:
        messages.error(request, f'خطا در انتخاب مدل: {str(e)}')
        return redirect('data_exflow:import')
    
    # Check file extension
    file_extension = get_file_extension(file.name)
    if not is_valid_file_type(file_extension):
        messages.error(request, f'فرمت فایل {file_extension} پشتیبانی نمی‌شود. فرمت‌های مجاز: .xlsx, .xls, .csv')
        return redirect('data_exflow:import')
    
    # Check file size
    try:
        check_file_size(file)
    except ValueError as e:
        messages.error(request, f'خطای حجم فایل: {str(e)}')
        return redirect('data_exflow:import')
    
    try:
        # Create import session
        session = ImportExportSession.objects.create(
            session_type=ImportExportSession.IMPORT,
            user=request.user,
            content_type=content_type,
            file=file,
            file_name=file.name,
            file_type=file_extension.replace('.', ''),
            status=ImportExportSession.PENDING
        )
        
        # Log file upload
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.INFO,
            message=f"File '{file.name}' uploaded for {content_type.model} import"
        )
        
        messages.success(request, f'فایل «{file.name}» با موفقیت آپلود شد. لطفاً فیلدها را مپ کنید.')
        return redirect('data_exflow:import_preview', session_id=session.id)
    except Exception as e:
        messages.error(request, f'خطا در آپلود فایل: {str(e)}')
        logger.warning(f"Error in import_upload: {str(e)}")
        return redirect('data_exflow:import')


@login_required
@role_required('admin','logistics_manager') 
def import_preview(request, session_id):
    """Preview the uploaded file contents."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    # Read the file
    file_path = session.file.path
    file_extension = get_file_extension(session.file_name)
    
    try:
        logger.info(f"DEBUG: Reading file: {file_path}")
        logger.info(f"DEBUG: File extension: {file_extension}")
        df = read_file_to_dataframe(file_path, file_extension)
        logger.info(f"DEBUG: DataFrame shape: {df.shape}")
        logger.info(f"DEBUG: DataFrame columns: {df.columns.tolist()}")
        logger.info(f"DEBUG: First few rows:")
        logger.info(df.head())
        
        # Convert dataframe to JSON for template
        preview_data = {
            'columns': df.columns.tolist(),
            'rows': df.head(10).replace({np.nan: None}).to_dict('records'),
            'total_rows': len(df)
        }
        
        logger.info(f"DEBUG: Preview data columns: {preview_data['columns']}")
        logger.info(f"DEBUG: Preview data rows count: {len(preview_data['rows'])}")
        logger.info(f"DEBUG: First row: {preview_data['rows'][0] if preview_data['rows'] else 'No rows'}")

        # Get model fields for mapping
        model_class = session.get_model_class()
        logger.info(f"DEBUG: Model class: {model_class}")
        fields = get_model_fields(model_class._meta.app_label, model_class.__name__)
        logger.info(f"DEBUG: Model fields count: {len(fields)}")
        
        context = {
            'title': 'Preview Import Data',
            'session': session,
            'preview': preview_data,
            'model_fields': fields,
            'standalone': True,
        }
        
        return render(request, 'data_exflow/import_preview.html', context)
    except Exception as e:
        import traceback
        logger.warning(f"Traceback: {traceback.format_exc()}")
        messages.error(request, f'Error reading file: {str(e)}')
        return redirect('data_exflow:import')


@login_required
@role_required('admin','logistics_manager') 
def import_map_fields(request, session_id):
    """Map file columns to model fields."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    if request.method != 'POST':
        return redirect('data_exflow:import_preview', session_id=session.id)
    
    # Get mapping data from form
    mapping = {}
    identifier_field = request.POST.get('identifier_field')
    
    # Read the file to get columns
    file_path = session.file.path
    file_extension = get_file_extension(session.file_name)
    df = read_file_to_dataframe(file_path, file_extension)
    columns = df.columns.tolist()
    
    # Process edited data and deleted rows
    edited_data_json = request.POST.get('edited_data', '{}')
    deleted_rows_json = request.POST.get('deleted_rows', '[]')
    
    try:
        edited_data = json.loads(edited_data_json) if edited_data_json else {}
        deleted_rows = json.loads(deleted_rows_json) if deleted_rows_json else []
        deleted_rows = set(map(int, deleted_rows))  # Convert to set of integers
        
        # Apply edits to dataframe
        if edited_data:
            for row_index, changes in edited_data.items():
                row_idx = int(row_index)
                if row_idx < len(df):
                    for column, new_value in changes.items():
                        if column in df.columns:
                            df.iloc[row_idx, df.columns.get_loc(column)] = new_value
            
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.INFO,
                message=f"Applied edits to {len(edited_data)} rows"
            )
        
        # Remove deleted rows
        if deleted_rows:
            # Sort in descending order to avoid index shifting issues
            sorted_deleted_rows = sorted(deleted_rows, reverse=True)
            for row_idx in sorted_deleted_rows:
                if row_idx < len(df):
                    df = df.drop(df.index[row_idx])
            
            # Reset index after dropping rows
            df = df.reset_index(drop=True)
            
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.INFO,
                message=f"Removed {len(deleted_rows)} rows from import data"
            )
        
        # Save the modified dataframe back to file
        if edited_data or deleted_rows:
            # Create a temporary file with the modified data
            import tempfile
            import os
            
            temp_dir = tempfile.mkdtemp()
            temp_filename = f"modified_{session.file_name}"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            # Save based on file type
            if file_extension.lower() in ['.xlsx', '.xls']:
                df.to_excel(temp_path, index=False)
            else:  # CSV
                df.to_csv(temp_path, index=False, encoding='utf-8')
            
            # Replace the original file
            import shutil
            shutil.move(temp_path, file_path)
            
            # Update session row count
            session.row_count = len(df)
            session.save()
            
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except (json.JSONDecodeError, ValueError) as e:
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.WARNING,
            message=f"Could not process edited data: {str(e)}"
        )
    
    # Process field mapping
    for column in columns:
        model_field = request.POST.get(f'map_{column}')
        if model_field and model_field != 'ignore':
            mapping[column] = {
                'model_field': model_field,
                'is_identifier': column == identifier_field
            }
    
    # Save mapping to session
    session.mapping = mapping
    session.save()
    
    # Log mapping
    ImportExportLog.objects.create(
        session=session,
        log_level=ImportExportLog.INFO,
        message=f"Field mapping created with {len(mapping)} fields"
    )
    
    return redirect('data_exflow:import_validate', session_id=session.id)


@login_required
@role_required('admin','logistics_manager')  
def import_validate(request, session_id):
    """Validate the import data against the model."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'نوع جلسه نامعتبر است')
        return redirect('data_exflow:import')
    
    if not session.mapping:
        messages.error(request, 'نگاشت فیلدها یافت نشد. لطفا ابتدا فیلدها را نگاشت کنید')
        return redirect('data_exflow:import_preview', session_id=session.id)
    
    # Update session status
    session.status = ImportExportSession.VALIDATING
    session.save()
    
    # Read the file
    file_path = session.file.path
    file_extension = get_file_extension(session.file_name)
    
    try:
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Validate data
        validation_result = validate_import_data(session, df, session.mapping)
        
        # Update session status
        session.status = ImportExportSession.VALIDATED if validation_result['valid'] else ImportExportSession.FAILED
        session.save()
        
        # Log validation results
        if validation_result['valid']:
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.SUCCESS,
                message=f"اعتبارسنجی موفق. {validation_result['creates']} رکورد برای ایجاد، {validation_result['updates']} رکورد برای به‌روزرسانی."
            )
            messages.success(request, f"اعتبارسنجی موفق. {validation_result['creates']} رکورد برای ایجاد، {validation_result['updates']} رکورد برای به‌روزرسانی.")
        else:
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.ERROR,
                message=f"اعتبارسنجی ناموفق با {len(validation_result['errors'])} خطا."
            )
            logger.warning(f"Validation failed with {len(validation_result['errors'])} errors. user: {request.user}, ip: {get_client_ip(request)}")
            messages.error(request, f"اعتبارسنجی ناموفق با {len(validation_result['errors'])} خطا. لطفا خطاها را برطرف کنید.")
            
            # Log each error
            for error in validation_result['errors']:
                ImportExportLog.objects.create(
                    session=session,
                    log_level=ImportExportLog.ERROR,
                    message=f"ردیف {error['row']}: " + ", ".join([e['message'] for e in error['errors']]),
                    row_number=error['row']
                )
        
        # Prepare warning logs
        for warning in validation_result.get('warnings', []):
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.WARNING,
                message=warning['message'],
                row_number=warning['row']
            )
        
        context = {
            'title': 'اعتبارسنجی داده‌ها',
            'session': session,
            'validation': validation_result,
            'logs': ImportExportLog.objects.filter(session=session).order_by('-created_at')[:20],
            'standalone': True,
        }
        
        return render(request, 'data_exflow/import_validate.html', context)
        
    except Exception as e:
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"خطای اعتبارسنجی: {str(e)}"
        )
        logger.warning(f"خطای اعتبارسنجی: {str(e)}. user: {request.user}, ip: {get_client_ip(request)}")
        
        messages.error(request, f'خطای اعتبارسنجی: {str(e)}')
        return redirect('data_exflow:import')


@login_required
@role_required('admin','logistics_manager') 
def import_process(request, session_id):
    """Process the import operation."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'نوع جلسه نامعتبر است')
        return redirect('data_exflow:import')
    
    if session.status != ImportExportSession.VALIDATED:
        messages.error(request, 'جلسه اعتبارسنجی نشده است. لطفا ابتدا داده‌ها را اعتبارسنجی کنید')
        return redirect('data_exflow:import_validate', session_id=session.id)
    
    if request.method != 'POST':
        return redirect('data_exflow:import_validate', session_id=session.id)
    
    try:
        # Process the import
        process_import(session)
        
        messages.success(request, 'عملیات ایمپورت با موفقیت انجام شد')
        return redirect('data_exflow:import_results', session_id=session.id)
        
    except ValueError as e:
        # Handle specific error types with user-friendly messages
        if "already being processed" in str(e):
            messages.error(request, 'این جلسه در حال حاضر توسط درخواست دیگری در حال پردازش است. لطفا بعدا تلاش کنید')
        else:
            messages.error(request, f'خطا در پردازش ایمپورت: {str(e)}')
            
        # Log the error
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"خطا در پردازش ایمپورت: {str(e)}"
        )
        logger.warning(f"خطای پردازش ایمپورت: {str(e)}.")
        
        session.status = ImportExportSession.FAILED
        session.save()
        
        return redirect('data_exflow:import_validate', session_id=session.id)
    except Exception as e:
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"خطای پردازش ایمپورت: {str(e)}"
        )
        logger.warning(f"خطای پردازش ایمپورت: {str(e)}.")
        messages.error(request, f'خطای پردازش ایمپورت: {str(e)}')
        return redirect('data_exflow:import_validate', session_id=session.id)


@login_required
@role_required('admin','logistics_manager') 
def import_results(request, session_id):
    """Show import results."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    # Get logs
    logs = ImportExportLog.objects.filter(session=session).order_by('-created_at')
    
    # Get import records
    import_records = ImportRecord.objects.filter(session=session).order_by('row_number')
    
    context = {
        'title': 'Import Results',
        'session': session,
        'logs': logs,
        'records': import_records,
        'success_count': import_records.filter(action='create').count() + import_records.filter(action='update').count(),
        'create_count': import_records.filter(action='create').count(),
        'update_count': import_records.filter(action='update').count(),
        'standalone': True,
    }
    
    return render(request, 'data_exflow/import_results.html', context)


@login_required
@role_required('admin','logistics_manager') 
def import_revert(request, session_id):
    """Revert an import operation."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'نوع جلسه نامعتبر است')
        return redirect('data_exflow:import')
    
    if not session.can_be_reverted:
        messages.error(request, 'این جلسه قابل بازگشت نیست. فقط جلسه‌های ایمپورت موفق قابل بازگشت هستند')
        return redirect('data_exflow:import_results', session_id=session.id)
    
    if request.method != 'POST':
        return redirect('data_exflow:import_results', session_id=session.id)
    
    try:
        # Revert the import
        revert_import(session)
        
        messages.success(request, 'بازگشت ایمپورت با موفقیت انجام شد')
        return redirect('data_exflow:import_results', session_id=session.id)
    
    except ValueError as e:
        # Handle specific error types with user-friendly messages
        if "already being processed" in str(e):
            messages.error(request, 'این جلسه در حال حاضر توسط درخواست دیگری در حال پردازش است. لطفا بعدا تلاش کنید')
        elif "cannot be reverted" in str(e):
            messages.error(request, 'این جلسه قابل بازگشت نیست')
        else:
            messages.error(request, f'خطا در بازگشت ایمپورت: {str(e)}')
            
        # Log the error
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"خطا در بازگشت ایمپورت: {str(e)}"
        )
        logger.warning(f"خطای بازگشت ایمپورت: {str(e)}.")
        
        return redirect('data_exflow:import_results', session_id=session.id)
    except Exception as e:
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"خطای بازگشت ایمپورت: {str(e)}"
        )

        
        messages.error(request, f'خطای بازگشت ایمپورت: {str(e)}')
        return redirect('data_exflow:import_results', session_id=session.id)


# ---------------------------
# Export Views
# ---------------------------

@login_required
@role_required('admin','logistics_manager') 
def export_view(request):
    """Main export view showing available models to export."""
    # Get all registered models organized by app
    models_by_app = get_all_registered_models()
    
    # Get recent exports
    recent_exports = ImportExportSession.objects.filter(
        session_type=ImportExportSession.EXPORT,
        user=request.user,
        status=ImportExportSession.COMPLETED
    ).order_by('-created_at')[:5]
    
    context = {
        'title': 'Export Data',
        'available_models': models_by_app,
        'recent_exports': recent_exports,
        'standalone': True,
    }
    
    return render(request, 'data_exflow/export.html', context)


@login_required
@role_required('admin','logistics_manager') 
def export_select_fields(request):
    """Select fields to export."""
    if request.method != 'POST':
        return redirect('data_exflow:export')
    
    # Get selected models - could be a list or a single value
    selected_models = request.POST.getlist('models')
    if not selected_models and request.POST.get('models'):
        selected_models = [request.POST.get('models')]
    
    if not selected_models:
        messages.error(request, 'لطفاً حداقل یک مدل انتخاب کنید')
        return redirect('data_exflow:export')
    
    # Get content types
    content_types = []
    model_fields = {}
    
    for ct_id in selected_models:
        try:
            ct = validate_content_type(ct_id)
            content_types.append(ct)
            
            model_class = ct.model_class()
            fields = get_model_fields(model_class._meta.app_label, model_class.__name__)
            
            model_fields[f"{ct.app_label}.{ct.model}"] = fields
            
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('data_exflow:export')
    
    context = {
        'title': 'انتخاب فیلدهای خروجی',
        'content_types': content_types,
        'model_fields': model_fields,
        'selected_model_ids': selected_models,
        'export_format': request.POST.get('format', 'xlsx'),
        'export_type': request.POST.get('export_type', 'all'),
        'selected_models': [{'content_type_id': ct.id, 'verbose_name': ct.model_class()._meta.verbose_name} for ct in content_types],
        'standalone': True,
    }
    
    return render(request, 'data_exflow/export_select_fields.html', context)


@login_required
@role_required('admin','logistics_manager') 
def export_confirm(request):
    """Confirm export settings and process the export."""
    if request.method != 'POST':
        return redirect('data_exflow:export')
    
    # Get form data
    field_mapping = {}
    content_types = []
    export_format = request.POST.get('export_format', 'xlsx')
    
    # Process field selections from form data
    for key, value in request.POST.items():
        if key.startswith('field_'):
            # Parse the field key - format: field_modelId_fieldName
            parts = key.split('_', 2)
            if len(parts) < 3:
                continue
                
            model_id = parts[1]
            field_name = parts[2]
            
            try:
                ct = ContentType.objects.get(id=model_id)
                model_key = f"{ct.app_label}.{ct.model}"
                
                if model_key not in field_mapping:
                    field_mapping[model_key] = {}
                    content_types.append(ct)
                
                # Use the field value (display name) for the mapping
                field_mapping[model_key][field_name] = value
            except ContentType.DoesNotExist:
                continue
    
    if not content_types or not field_mapping:
        messages.error(request, 'No fields selected for export')
        return redirect('data_exflow:export')
    
    try:
        # Process the export
        session = process_export(content_types, field_mapping, request.user, format=export_format)
        
        # Redirect to download page
        return redirect('data_exflow:export_download', session_id=session.id)
        
    except Exception as e:
        messages.error(request, f'Export error: {str(e)}')
        return redirect('data_exflow:export')


@login_required
@role_required('admin','logistics_manager') 
def export_download(request, session_id):
    """Show download page for the exported file."""
    logger.warning(f"Export download called by {get_client_ip(request)}, user: {request.user}")
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.EXPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:export')
    
    if not session.file:
        messages.error(request, 'No export file found')
        return redirect('data_exflow:export')
    
    # Get file size
    try:
        file_size_bytes = session.file.size
        if file_size_bytes < 1024:
            file_size = f"{file_size_bytes} B"
        elif file_size_bytes < 1024 * 1024:
            file_size = f"{file_size_bytes/1024:.1f} KB"
        else:
            file_size = f"{file_size_bytes/(1024*1024):.1f} MB"
    except:
        file_size = "N/A"
    
    # Get selected models and field count
    content_types = []
    field_count = 0
    exported_fields = []
    
    if session.mapping:
        for model_key, fields in session.mapping.items():
            app_label, model_name = model_key.split('.')
            try:
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
                content_types.append({
                    'verbose_name': ct.model_class()._meta.verbose_name
                })
                
                for field_name, field_label in fields.items():
                    field_count += 1
                    exported_fields.append({
                        'name': field_label,
                        'model': ct.model_class()._meta.verbose_name
                    })
            except:
                continue
    
    context = {
        'title': 'Download Export',
        'session': session,
        'export_filename': session.file_name,
        'export_file_url': session.file.url,
        'export_format': session.file_type,
        'export_date': session.created_at,
        'file_size': file_size,
        'record_count': session.row_count or 0,
        'field_count': field_count,
        'selected_models': content_types,
        'exported_fields': exported_fields,
        'standalone': True,
    }
    
    return render(request, 'data_exflow/export_download.html', context)


@login_required
@role_required('admin','logistics_manager') 
def export_process(request):
    """Process the export operation."""
    if request.method != 'POST':
        return redirect('data_exflow:export')
    
    # Get form data
    field_mapping = {}
    content_types = []
    
    # Process all models and their fields
    for key, value in request.POST.items():
        if key.startswith('field_'):
            # Format: field_app-label_model_fieldname
            _, app_label, model, field_name = key.split('_', 3)
            
            model_key = f"{app_label}.{model}"
            if model_key not in field_mapping:
                field_mapping[model_key] = {}
                
                # Add content type
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model)
                    content_types.append(ct)
                except ContentType.DoesNotExist:
                    continue
            
            # Add field mapping with the exported name as value
            field_mapping[model_key][field_name] = value
    
    if not content_types or not field_mapping:
        messages.error(request, 'No fields selected for export')
        return redirect('data_exflow:export')
    
    try:
        # Process the export
        session = process_export(content_types, field_mapping, request.user)
        
        # Serve the file
        response = HttpResponse(
            session.file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{session.file_name}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Export error: {str(e)}')
        return redirect('data_exflow:export')


# ---------------------------
# API Views
# ---------------------------

@login_required
@role_required('admin','logistics_manager') 
def api_get_models(request):
    """API endpoint to get all registered models."""
    models = get_all_registered_models()
    return JsonResponse(models)


@login_required
@role_required('admin','logistics_manager') 
def api_get_model_fields(request, app_label=None, model_name=None):
    """API endpoint for getting model fields."""
    # Get content type ID from URL or query param
    content_type_id = request.GET.get('content_type_id')
    
    try:
        if content_type_id:
            content_type = ContentType.objects.get(id=content_type_id)
            app_label = content_type.app_label
            model_name = content_type.model
        elif not app_label or not model_name:
            return JsonResponse({'error': 'Must provide app_label and model_name or content_type_id'}, status=400)
        
        # Get model class
        model = apps.get_model(app_label, model_name)
        
        fields = []
        # Get model fields
        for field in model._meta.fields:
            # Skip hidden fields
            if field.name.startswith('_'):
                continue
                
            # Get basic field info
            field_info = {
                'name': field.name,
                'verbose_name': field.verbose_name,
                'type': field.get_internal_type(),
                'required': not field.null and not field.blank and not field.primary_key and not field.has_default(),
                'primary_key': field.primary_key,
                'unique': field.unique,
                'has_choices': bool(field.choices),
                'choices': [],
                'default': None,
                'has_default': field.has_default(),
                'default_value': None,
            }
            
            # Handle default values
            if field.has_default():
                try:
                    default_value = field.get_default()
                    # Handle callables (like functions, etc)
                    if callable(default_value):
                        try:
                            default_value = default_value()
                        except:
                            default_value = str(default_value)
                    # Convert the default value to string representation
                    field_info['default_value'] = str(default_value)
                except Exception as e:
                    field_info['default_value'] = f"(error getting default: {str(e)})"
            
            # Handle choices fields
            if field.choices:
                for key, display in field.choices:
                    # Check if the choice is a tuple of tuples (for grouped choices)
                    if isinstance(display, (list, tuple)):
                        for subkey, subdisplay in display:
                            field_info['choices'].append({
                                'key': str(subkey),
                                'display': str(subdisplay)
                            })
                    else:
                        field_info['choices'].append({
                            'key': str(key),
                            'display': str(display)
                        })
            
            # Handle ForeignKey fields
            if field.get_internal_type() == 'ForeignKey':
                related_model_meta = field.related_model._meta
                field_info['related_model'] = {
                    'app_label': related_model_meta.app_label,
                    'model_name': related_model_meta.model_name,
                    'verbose_name': str(related_model_meta.verbose_name),
                }
                
                # If the related model has a __str__ method, get some sample values
                try:
                    sample_instances = field.related_model.objects.all()[:10]
                    field_info['related_model']['sample_values'] = []
                    for instance in sample_instances:
                        field_info['related_model']['sample_values'].append({
                            'id': instance.pk,
                            'display': str(instance)
                        })
                except Exception as e:
                    logger.info(f"Error getting sample values for {field.name}: {e}")
                
                # If the related model has a choices attribute, add them
                if hasattr(field.related_model, 'CHOICES') or hasattr(field.related_model, 'choices'):
                    choices_attr = getattr(field.related_model, 'CHOICES', None) or getattr(field.related_model, 'choices', None)
                    if choices_attr:
                        field_info['choices'] = [{'key': str(key), 'display': str(display)} 
                                                for key, display in choices_attr]
            
            # Special handling for specific model types like CargoProduct
            if field.related_model and field.related_model.__name__ == 'CargoProduct':
                try:
                    # Add product types
                    product_types = field.related_model.PRODUCT_TYPES
                    field_info['product_types'] = [{'key': str(key), 'display': str(display)} 
                                               for key, display in product_types]
                    
                    # Add countries
                    countries = field.related_model.COUNTRIES
                    field_info['countries'] = [{'key': str(key), 'display': str(display)} 
                                           for key, display in countries]
                except Exception as e:
                    logger.info(f"Error getting CargoProduct info: {e}")
            
            fields.append(field_info)
        
        # Get many-to-many fields
        for field in model._meta.many_to_many:
            field_info = {
                'name': field.name,
                'verbose_name': field.verbose_name,
                'type': 'ManyToManyField',
                'required': False,  # M2M fields are never required
                'primary_key': False,
                'unique': False,
                'has_choices': False,
                'choices': [],
                'related_model': {
                    'app_label': field.related_model._meta.app_label,
                    'model_name': field.related_model._meta.model_name,
                    'verbose_name': str(field.related_model._meta.verbose_name),
                }
            }
            
            # If the related model has a __str__ method, get some sample values
            try:
                sample_instances = field.related_model.objects.all()[:10]
                field_info['related_model']['sample_values'] = []
                for instance in sample_instances:
                    field_info['related_model']['sample_values'].append({
                        'id': instance.pk,
                        'display': str(instance)
                    })
            except Exception as e:
                logger.info(f"Error getting sample values for {field.name}: {e}")
            
            fields.append(field_info)
            
        # Add any model-level choices if they exist
        model_choices = {}
        for attr_name in dir(model):
            if attr_name.endswith('_CHOICES') or attr_name.endswith('_TYPES'):
                try:
                    choices = getattr(model, attr_name)
                    if isinstance(choices, (list, tuple)) and choices and isinstance(choices[0], (list, tuple)):
                        model_choices[attr_name] = [{'key': str(key), 'display': str(display)} 
                                                  for key, display in choices]
                except:
                    pass
        
        return JsonResponse({
            'model': {
                'app_label': app_label,
                'model_name': model_name,
                'verbose_name': str(model._meta.verbose_name),
            },
            'fields': fields,
            'model_choices': model_choices
        })
    
    except ContentType.DoesNotExist:
        return JsonResponse({'error': f'Content type not found: {content_type_id}'}, status=404)
    except LookupError:
        return JsonResponse({'error': f'Model not found: {app_label}.{model_name}'}, status=404)
    except Exception as e:
        logger.warning(f"Error in api_get_model_fields: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@role_required('admin','logistics_manager') 
def api_edit_cell(request, session_id):
    """API endpoint to edit a cell in the preview."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        return JsonResponse({'error': 'Invalid session type'}, status=400)
    
    try:
        data = json.loads(request.body)
        row = data.get('row')
        column = data.get('column')
        value = data.get('value')
        
        if row is None or column is None or value is None:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        # Validate input parameters
        if not isinstance(row, int) or row < 0:
            return JsonResponse({'error': 'Invalid row number'}, status=400)
            
        if not isinstance(column, str) or not column:
            return JsonResponse({'error': 'Invalid column name'}, status=400)
            
        # Value can be of various types, so we don't validate it strictly
        
        # Read the file
        file_path = session.file.path
        file_extension = get_file_extension(session.file_name)
        
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Update the cell value
        df.iloc[row, df.columns.get_loc(column)] = value
        
        # Create a temporary file to save the updated data
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
                temp_path = tmp.name
                
            # Save the dataframe to the temporary file
            if file_extension in ['.xlsx', '.xls']:
                df.to_excel(temp_path, index=False)
            elif file_extension == '.csv':
                df.to_csv(temp_path, index=False)
            
            # Save the updated file
            with open(temp_path, 'rb') as f:
                session.file.save(session.file_name, f)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
        finally:
            # Always clean up the temporary file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass  # Log this error but don't fail if cleanup fails
        
    except Exception as e:

        return JsonResponse({'error': str(e)}, status=500)


@login_required
@role_required('admin','logistics_manager') 
def api_list_contenttypes(request):
    """API endpoint to list all content types."""
    try:
        from django.contrib.contenttypes.models import ContentType
        
        # Get all content types
        contenttypes = ContentType.objects.all().order_by('app_label', 'model')
        
        # Format data for JSON response
        data = []
        for ct in contenttypes:
            data.append({
                'id': ct.id,
                'app_label': ct.app_label,
                'model': ct.model,
                'name': str(ct)
            })
        
        return JsonResponse({'contenttypes': data})
    except Exception as e:
        import traceback
        logger.warning(f"Error in api_list_contenttypes: {str(e)}, traceback: {traceback.format_exc()}")
        return JsonResponse({
            'error': f'Error listing content types: {str(e)}'
        }, status=500)


@login_required
@role_required('admin','logistics_manager')      
def download_sample_file(request):
    """Download a sample file with valid choices values."""
    content_type_id = request.GET.get('content_type_id')
    file_format = request.GET.get('format', 'csv')  # Default to CSV
    
    if not content_type_id:
        messages.error(request, 'لطفاً مدل داده را انتخاب کنید')
        return redirect('data_exflow:import')
    
    try:
        # Get content type and model
        content_type = ContentType.objects.get(id=content_type_id)
        model_class = content_type.model_class()
        
        # Get fields info using the API directly
        app_label = content_type.app_label
        model_name = content_type.model
        
        # Capture API response for model fields
        api_response = api_get_model_fields(request, app_label=app_label, model_name=model_name)
        api_data = json.loads(api_response.content)
        
        fields = api_data.get('fields', [])
        
        # Create a DataFrame with sample data
        sample_data = {}
        
        for field in fields:
            field_name = field['name']
            field_verbose_name = field.get('verbose_name', field_name)
            
            # Skip some technical fields
            if field_name in ['id', '_state', 'pk'] or field_name.startswith('_'):
                continue
                
            # Skip many-to-many fields and reverse relations
            if field.get('type') in ['ManyToManyField', 'OneToOneRel', 'ManyToOneRel']:
                continue
            
            # Handle different field types
            if field.get('has_choices', False) and field.get('choices'):
                # Use the first choice as an example
                if field['choices']:
                    choice = field['choices'][0]
                    sample_data[field_name] = f"{choice['key']}"  # Just use the key for simplicity
                else:
                    sample_data[field_name] = ""
            elif field.get('type') == 'ForeignKey' and field.get('related_model'):
                # For ForeignKey, suggest using ID of a sample instance if available
                if field.get('related_model', {}).get('sample_values', []):
                    sample_instance = field['related_model']['sample_values'][0]
                    sample_data[field_name] = f"{sample_instance['id']}"
                else:
                    sample_data[field_name] = f"ID از {field['related_model']['verbose_name']}"
            elif field.get('type') == 'DateField':
                sample_data[field_name] = "1402-01-01"
            elif field.get('type') == 'DateTimeField':
                sample_data[field_name] = "1402-01-01 12:00:00"
            elif field.get('type') in ['IntegerField', 'PositiveIntegerField', 'PositiveSmallIntegerField', 'BigIntegerField']:
                sample_data[field_name] = "123"
            elif field.get('type') in ['DecimalField', 'FloatField']:
                sample_data[field_name] = "123.45"
            elif field.get('type') == 'BooleanField':
                # Check for default value
                if field.get('has_default'):
                    default_value = field.get('default_value', 'False')
                    sample_data[field_name] = default_value
                else:
                    sample_data[field_name] = "True"
            else:
                # Add default value if available
                if field.get('has_default') and field.get('default_value'):
                    sample_data[field_name] = field['default_value']
                else:
                    sample_data[field_name] = f"نمونه {field_verbose_name}"
        
        # Create a DataFrame with the sample data
        df = pd.DataFrame([sample_data])
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_format}') as tmp:
            temp_path = tmp.name
            
        # Save based on format
        if file_format == 'xlsx':
            # For Excel, create a workbook and set RTL for the sheet
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils.dataframe import dataframe_to_rows
            
            wb = Workbook()
            ws = wb.active
            ws.title = f"نمونه {model_class._meta.verbose_name}"
            ws.sheet_properties.rightToLeft = True  # Enable RTL for Excel sheet
            
            # Define styles
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            
            data_font = Font()
            data_alignment = Alignment(horizontal="right", vertical="center")
            
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Add headers first
            headers = list(sample_data.keys())
            ws.append(headers)
            
            # Style header row
            for cell in ws[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = border
            
            # Add data row
            data_row = list(sample_data.values())
            ws.append(data_row)
            
            # Style data row
            for cell in ws[2]:
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = border
            
            # Adjust column widths
            for i, column in enumerate(ws.columns, 1):
                max_length = 0
                column_letter = get_column_letter(i)
                
                for cell in column:
                    if cell.value:
                        cell_length = len(str(cell.value))
                        max_length = max(max_length, cell_length)
                
                adjusted_width = max(max_length + 4, 15)  # Add padding and minimum width
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Add a note sheet with field information
            note_sheet = wb.create_sheet("راهنمای فیلدها")
            note_sheet.sheet_properties.rightToLeft = True
            
            # Add field information
            note_sheet.append(["نام فیلد", "نوع فیلد", "توضیحات", "مقادیر مجاز"])
            
            # Style note headers
            for cell in note_sheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = border
            
            # Add field details
            for field in fields:
                field_name = field['name']
                field_type = field.get('type', 'نامشخص')
                field_verbose = field.get('verbose_name', field_name)
                
                # Skip technical fields
                if field_name in ['id', '_state', 'pk'] or field_name.startswith('_'):
                    continue
                if field.get('type') in ['ManyToManyField', 'OneToOneRel', 'ManyToOneRel']:
                    continue
                
                # Get choices or sample values
                choices_text = ""
                if field.get('has_choices', False) and field.get('choices'):
                    choices_list = [f"{choice['key']} ({choice['display']})" for choice in field['choices']]
                    choices_text = "، ".join(choices_list[:5])  # Limit to first 5 choices
                    if len(field['choices']) > 5:
                        choices_text += "..."
                elif field.get('type') == 'ForeignKey' and field.get('related_model'):
                    if field.get('related_model', {}).get('sample_values', []):
                        sample_values = [str(val['id']) for val in field['related_model']['sample_values'][:3]]
                        choices_text = f"ID های موجود: {', '.join(sample_values)}"
                    else:
                        choices_text = f"ID از {field['related_model']['verbose_name']}"
                
                note_sheet.append([field_name, field_type, field_verbose, choices_text])
            
            # Style note data rows
            for row in note_sheet.iter_rows(min_row=2):
                for cell in row:
                    cell.font = data_font
                    cell.alignment = data_alignment
                    cell.border = border
            
            # Adjust note sheet column widths
            for i, column in enumerate(note_sheet.columns, 1):
                column_letter = get_column_letter(i)
                max_length = 0
                for cell in column:
                    if cell.value:
                        cell_length = len(str(cell.value))
                        max_length = max(max_length, cell_length)
                adjusted_width = max(max_length + 4, 20)
                note_sheet.column_dimensions[column_letter].width = adjusted_width
            
            # Save to temporary file
            wb.save(temp_path)
        else:  # Default to CSV
            # Create a more comprehensive CSV with field information
            csv_lines = []
            
            # Add header with field information
            csv_lines.append("# فایل نمونه برای مدل: " + model_class._meta.verbose_name)
            csv_lines.append("# این فایل شامل مقادیر نمونه و راهنمای فیلدها است")
            csv_lines.append("#")
            
            # Add field information as comments
            csv_lines.append("# اطلاعات فیلدها:")
            for field in fields:
                field_name = field['name']
                field_type = field.get('type', 'نامشخص')
                field_verbose = field.get('verbose_name', field_name)
                
                # Skip technical fields
                if field_name in ['id', '_state', 'pk'] or field_name.startswith('_'):
                    continue
                if field.get('type') in ['ManyToManyField', 'OneToOneRel', 'ManyToOneRel']:
                    continue
                
                # Get choices or sample values
                choices_text = ""
                if field.get('has_choices', False) and field.get('choices'):
                    choices_list = [f"{choice['key']} ({choice['display']})" for choice in field['choices']]
                    choices_text = "، ".join(choices_list[:5])
                    if len(field['choices']) > 5:
                        choices_text += "..."
                elif field.get('type') == 'ForeignKey' and field.get('related_model'):
                    if field.get('related_model', {}).get('sample_values', []):
                        sample_values = [str(val['id']) for val in field['related_model']['sample_values'][:3]]
                        choices_text = f"ID های موجود: {', '.join(sample_values)}"
                    else:
                        choices_text = f"ID از {field['related_model']['verbose_name']}"
                
                csv_lines.append(f"# {field_name} ({field_type}): {field_verbose} - {choices_text}")
            
            csv_lines.append("#")
            csv_lines.append("# داده نمونه:")
            
            # Add UTF-8 BOM for better Excel CSV support of Unicode
            with open(temp_path, 'w', encoding='utf-8-sig', newline='') as f:
                # Write comments first
                for line in csv_lines:
                    f.write(line + '\n')
                
                # Then write the actual CSV data
                df.to_csv(f, index=False)
            
        # Create response
        with open(temp_path, 'rb') as f:
            file_data = f.read()
            
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        
        # Set response headers
        response = HttpResponse(
            file_data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if file_format == 'xlsx' else 'text/csv'
        )
        
        # Set filename with correct encoding for Persian characters
        filename = f"نمونه_{model_class._meta.verbose_name}.{file_format}"
        encoded_filename = quote(filename)
        response['Content-Disposition'] = f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        return response
    except Exception as e:
        import traceback
        logger.warning(f"Error in download_sample_file: {str(e)}, traceback: {traceback.format_exc()}")
        messages.error(request, f'خطا در ایجاد فایل نمونه: {str(e)}')
        return redirect('data_exflow:import')
