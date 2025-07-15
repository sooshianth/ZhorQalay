from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models.BarnamehModel import Barnameh
from .models.ExcelFileModel import ExcelFile
from .models.ApiLogModel import BKIApiLog
from core.decorators.decorators import role_required
from .API.insertBarnameh import send_barnameh_to_bki, send_multiple_barnameh_to_bki
from .API.EditBarnameh import edit_barnameh_api
from .API.EstelameBarnameh import estelame_barnameh
from .excel_management.views import get_client_ip
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
import json
import os
from django.conf import settings
import pandas as pd
from datetime import datetime
import logging
import jdatetime
import logging

logger = logging.getLogger("bki_barnameh_views")
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse

# توابع اکسل به فولدر excel_management منتقل شده‌اند
from .excel_management.views import upload_excel_view, download_excel_template, export_excel_view

logger = logging.getLogger('bki_barnameh_views')

# تعریف تمام ستون‌های قابل نمایش در جدول بارنامه
BARNAMEH_COLUMNS = [
    {'id': 'number', 'name': 'شماره بارنامه'},
    {'id': 'serial', 'name': 'سریال بارنامه'},
    {'id': 'tonnage', 'name': 'وزن'},
    {'id': 'status', 'name': 'وضعیت'},
    {'id': 'driver_name', 'name': 'نام راننده'},
    {'id': 'driver_phone', 'name': 'شماره راننده'},
    {'id': 'vehicle_plate', 'name': 'پلاک خودرو'},
    {'id': 'receiver_name', 'name': 'نام گیرنده'},
    {'id': 'destination', 'name': 'مقصد'},
    {'id': 'barnameh_date', 'name': 'تاریخ بارنامه'},
    {'id': 'transport_date', 'name': 'تاریخ حمل'},
    {'id': 'purchase_number', 'name': 'شماره خرید'},
    {'id': 'shenase_takhsis_code', 'name': 'شناسه تخصیص'},
    {'id': 'cargo', 'name': 'کوتاژ'},
    {'id': 'company_price', 'name': 'فی خرید'},
    {'id': 'customer_price', 'name': 'فی فروش'},
    {'id': 'total_sales_amount', 'name': 'مبلغ کل فروش'},
    {'id': 'buyer_national_code', 'name': 'شماره ملی خریدار'},
    {'id': 'buyer_postal_code', 'name': 'کدپستی خریدار'},
    {'id': 'buyer_address', 'name': 'آدرس خریدار'},
    {'id': 'demand_amount', 'name': 'میزان تقاضا'},
    {'id': 'importer', 'name': 'واردکننده'},
    {'id': 'product_type', 'name': 'محصول'},
    {'id': 'successful_send_date', 'name': 'تاریخ ارسال موفق به بازارگاه'},
    {'id': 'is_sent_to_bki', 'name': 'ارسال به بازارگاه'},
    {'id': 'created_at', 'name': 'تاریخ ایجاد'},
    {'id': 'actions', 'name': 'عملیات'},
    {'id': 'factor_sodoor_season', 'name': 'زمان صدور فاکتور فصل'},
    {'id': 'is_factored', 'name': 'فاکتور صادر شده'},
    {'id': 'is_sent_to_bki', 'name': 'ارسال به بازارگاه'},
    {'id': 'is_created_by_excel', 'name': 'ایجاد توسط اکسل'},
    {'id': 'is_sent_to_bki_at', 'name': 'تاریخ ارسال به بازارگاه'},
    {'id': 'is_created_by_excel_at', 'name': 'تاریخ ایجاد توسط اکسل'},
    {'id': 'barnameh_updated_at', 'name': 'تاریخ بروزرسانی'},
]

# ستون‌های پیش‌فرض
DEFAULT_BARNAMEH_COLUMNS = [
    'number', 'serial', 'tonnage', 'status', 'driver_name', 
    'barnameh_date', 'purchase_number', 'shenase_takhsis_code', 'actions'
]

def get_barnameh_columns_from_cookie(request):
    """دریافت ستون‌های انتخاب شده از کوکی"""
    columns = request.COOKIES.get('barnameh_selected_columns')
    if columns:
        try:
            return columns.split(',')
        except:
            pass
    return DEFAULT_BARNAMEH_COLUMNS.copy()

def get_all_barnameh_columns():
    """دریافت تمام ستون‌های موجود"""
    return BARNAMEH_COLUMNS

# Map table name to model for table_filter support
TABLE_MODEL_MAPPING = {
    'barnameh': Barnameh,
}

def get_model_from_table_name(table_name):
    """Return model class for given table name"""
    return TABLE_MODEL_MAPPING.get(table_name)

@csrf_exempt
@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["POST"])
def update_barnameh_columns(request):
    """API برای بروزرسانی ستون‌های انتخاب شده"""
    try:
        data = json.loads(request.body)
        selected_columns = data.get('columns', [])
        
        # اعتبارسنجی ستون‌ها
        valid_column_ids = [col['id'] for col in BARNAMEH_COLUMNS]
        selected_columns = [col for col in selected_columns if col in valid_column_ids]
        
        if not selected_columns:
            return JsonResponse({
                'status': 'error',
                'message': 'هیچ ستون معتبری انتخاب نشده است'
            })
        
        response = JsonResponse({
            'status': 'success',
            'message': 'ستون‌ها با موفقیت بروزرسانی شدند',
            'columns': selected_columns
        })
        
        # ذخیره در کوکی
        response.set_cookie(
            'barnameh_selected_columns',
            ','.join(selected_columns),
            max_age=365*24*60*60  # یک سال
        )
        
        return response
        
    except Exception as e:
        logger.error(f"خطا در بروزرسانی ستون‌های بارنامه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در بروزرسانی ستون‌ها: {str(e)}'
        }, status=500)

@csrf_exempt
@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["POST"])
def reset_barnameh_columns(request):
    """API برای بازگشت ستون‌ها به حالت پیش‌فرض"""
    try:
        response = JsonResponse({
            'status': 'success',
            'message': 'ستون‌ها به حالت پیش‌فرض بازگشت داده شدند',
            'columns': DEFAULT_BARNAMEH_COLUMNS
        })
        
        # پاک کردن کوکی
        response.delete_cookie('barnameh_selected_columns')
        
        return response
        
    except Exception as e:
        logger.error(f"خطا در بازگشت ستون‌های بارنامه به حالت پیش‌فرض: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در بازگشت ستون‌ها: {str(e)}'
        }, status=500)

@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["GET"])
def get_barnameh_columns_config(request):
    """API برای دریافت تنظیمات ستون‌های بارنامه"""
    try:
        selected_columns = get_barnameh_columns_from_cookie(request)
        
        return JsonResponse({
            'status': 'success',
            'all_columns': BARNAMEH_COLUMNS,
            'selected_columns': selected_columns,
            'default_columns': DEFAULT_BARNAMEH_COLUMNS
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت تنظیمات ستون‌های بارنامه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت تنظیمات: {str(e)}'
        }, status=500)

@csrf_exempt  
@role_required('logistics_manager', 'admin', 'financial_manager')
@login_required
def apply_barnameh_filter(request):
    """
    API برای اعمال فیلتر سمت سرور به بارنامه‌ها
    """
    logger.warning(f"درخواست فیلتر بارنامه توسط {request.user.username} انجام شده. {get_client_ip(request)}")
    try:
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        sort_config = json.loads(request.POST.get('sort', '{}'))
        # دریافت پارامترهای pagination
        page_param = request.POST.get('page', '1')
        per_page_param = request.POST.get('per_page', '50')
        # دریافت پارامتر جستجوی سریع
        global_search = request.POST.get('global_search', '')
        
        try:
            page = int(page_param)
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            logger.error(f"❌ مقادیر pagination نامعتبر: page={page_param}, per_page={per_page_param}")
            page = 1
            per_page = 50
        
        # ایجاد QuerySet پایه
        base_queryset = Barnameh.objects.select_related(
            'purchase', 'shenase_takhsis', 'purchase__cargo', 'purchase__cargo__vared_konandeh'
        )
        
        # اعمال فیلترها - فقط اگر فیلتر وجود داشته باشد
        if filters:
            filter_conditions = Q()
            
            for column_id, filter_data in filters.items():
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if column_id == 'number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(number__in=values)
                        else:
                            filter_conditions &= ~Q(number__in=values)
                        
                elif column_id == 'serial':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(serial__in=values)
                        else:
                            filter_conditions &= ~Q(serial__in=values)
                        
                elif column_id == 'purchase_number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(purchase_number__in=values)
                        
                elif column_id == 'status':
                    # تبدیل نمایش وضعیت به کد وضعیت
                    status_map = {
                        'بارنامه ناقص': 'BARNAMEH_INCOMPLETE',
                        'بارنامه کامل': 'BARNAMEH_COMPLETE',
                        'ارسال شده به بازارگاه': 'PURCHASE_CLOSED'
                    }
                    status_codes = []
                    for v in values:
                        if v in status_map:
                            status_codes.append(status_map[v])
                        else:
                            status_codes.append(v)
                    
                    if status_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(status__in=status_codes)
                        else:
                            filter_conditions &= ~Q(status__in=status_codes)
                        
                elif column_id in ['driver_name', 'driver_phone', 'vehicle_plate', 
                                 'receiver_name', 'destination', 'shenase_takhsis_code']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': values})
                
                elif column_id == 'tonnage':
                    # تبدیل به اعداد
                    numeric_values = []
                    for v in values:
                        try:
                            # حذف کاما و تبدیل به عدد
                            clean_value = str(v).replace(',', '').strip()
                            if clean_value:
                                numeric_values.append(float(clean_value))
                        except (ValueError, TypeError):
                            continue
                    
                    if numeric_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(tonnage__in=numeric_values)
                        else:
                            filter_conditions &= ~Q(tonnage__in=numeric_values)
                
                elif column_id == 'barnameh_date':
                    date_values = []
                    for v in values:
                        try:
                            # پارس تاریخ
                            if '/' in v:
                                date_obj = datetime.strptime(v, "%Y/%m/%d").date()
                                date_values.append(date_obj)
                        except (ValueError, TypeError):
                            continue
                    
                    if date_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(barnameh_date__in=date_values)
                        else:
                            filter_conditions &= ~Q(barnameh_date__in=date_values)
                
                elif column_id in ['is_sent_to_bki', 'is_factored', 'is_created_by_excel']:
                    bool_values = []
                    for v in values:
                        if v.lower() in ['بله', 'true', '1', 'yes']:
                            bool_values.append(True)
                        elif v.lower() in ['خیر', 'false', '0', 'no']:
                            bool_values.append(False)
                    
                    if bool_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': bool_values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': bool_values})
            
            # اعمال فیلترها
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع
        if global_search:
            search_conditions = (
                Q(number__icontains=global_search) |
                Q(serial__icontains=global_search) |
                Q(driver_name__icontains=global_search) |
                Q(driver_phone__icontains=global_search) |
                Q(vehicle_plate__icontains=global_search) |
                Q(receiver_name__icontains=global_search) |
                Q(destination__icontains=global_search) |
                Q(purchase_number__icontains=global_search) |
                Q(shenase_takhsis_code__icontains=global_search)
            )
            base_queryset = base_queryset.filter(search_conditions)
        
        # اعمال مرتب‌سازی
        if sort_config and sort_config.get('column'):
            sort_column = sort_config['column']
            sort_direction = sort_config.get('direction', 'asc')
            
            # تعیین نام فیلد برای مرتب‌سازی
            sort_field = sort_column
            if sort_direction == 'desc':
                sort_field = f'-{sort_field}'
                
            try:
                base_queryset = base_queryset.order_by(sort_field)
            except Exception as e:
                logger.warning(f"خطا در مرتب‌سازی: {e}")
                base_queryset = base_queryset.order_by('-barnameh_created_at')
        else:
            # مرتب‌سازی پیش‌فرض
            base_queryset = base_queryset.order_by('-barnameh_created_at')
        
        # اعمال pagination
        if per_page == 999999:  # نمایش همه
            page_obj = base_queryset
            total_count = base_queryset.count()
            paginator = None
        else:
            paginator = Paginator(base_queryset, per_page)
            try:
                page_obj = paginator.page(page)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)
                page = 1
            total_count = paginator.count
        
        # فرمت نتایج برای JSON response
        results = []
        for barnameh in page_obj:
            # Helper function to safely get related data
            def get_related_data(obj, attr_path, default=""):
                try:
                    current = obj
                    for attr in attr_path.split('.'):
                        if current is None:
                            return default
                        current = getattr(current, attr, None)
                    return current or default
                except (AttributeError, TypeError):
                    return default
            
            result = {
                'id': barnameh.id,
                'number': barnameh.number or "",
                'serial': barnameh.serial or "",
                'tonnage': barnameh.tonnage or 0,
                'status': barnameh.status,
                'status_display': barnameh.get_status_display() if hasattr(barnameh, 'get_status_display') else barnameh.status,
                'driver_name': barnameh.driver_name or "",
                'driver_phone': barnameh.driver_phone or "",
                'vehicle_plate': barnameh.vehicle_plate or "",
                'receiver_name': barnameh.receiver_name or "",
                'destination': barnameh.destination or "",
                'barnameh_date': barnameh.barnameh_date.strftime("%Y/%m/%d") if barnameh.barnameh_date else "",
                'transport_date': barnameh.transport_date.strftime("%Y/%m/%d") if barnameh.transport_date else "",
                'purchase_number': barnameh.purchase_number or "",
                'shenase_takhsis_code': barnameh.shenase_takhsis_code or "",
                'is_sent_to_bki': barnameh.is_sent_to_bki,
                'is_factored': barnameh.is_factored,
                'is_created_by_excel': barnameh.is_created_by_excel,
                'created_at': barnameh.barnameh_created_at.strftime("%Y/%m/%d") if hasattr(barnameh, 'barnameh_created_at') and barnameh.barnameh_created_at else "",
                'factor_sodoor_season': barnameh.factor_sodoor_season or "",
                'buyer_postal_code': barnameh.buyer_postal_code or "",
                # Related data from purchase
                'cargo': get_related_data(barnameh, 'purchase.cargo.cottage'),
                'company_price': get_related_data(barnameh, 'purchase.company_price'),
                'customer_price': get_related_data(barnameh, 'purchase.customer_price'),
                'total_sales_amount': get_related_data(barnameh, 'purchase.total_sales_amount'),
                'buyer_national_code': get_related_data(barnameh, 'purchase.buyer_national_code'),
                'buyer_address': get_related_data(barnameh, 'purchase.address'),
                'demand_amount': get_related_data(barnameh, 'purchase.total_weight'),
                'importer': get_related_data(barnameh, 'purchase.cargo.vared_konandeh.name'),
                'product_type': get_related_data(barnameh, 'purchase.cargo.product_type'),
                'successful_send_date': get_related_data(barnameh, 'purchase.successful_send_date'),
            }
            results.append(result)
        
        # اطلاعات pagination
        if paginator:
            pagination_info = {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': total_count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_size': per_page,
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index()
            }
        else:
            pagination_info = {
                'current_page': 1,
                'total_pages': 1,
                'total_count': total_count,
                'has_next': False,
                'has_previous': False,
                'page_size': total_count,
                'start_index': 1,
                'end_index': total_count
            }
        
        return JsonResponse({
            'status': 'success',
            'data': results,
            'total_count': total_count,
            'start_index': pagination_info['start_index'],
            'end_index': pagination_info['end_index'],
            'current_page': pagination_info['current_page'],
            'total_pages': pagination_info['total_pages'],
            'has_next': pagination_info['has_next'],
            'has_previous': pagination_info['has_previous'],
            'filter_applied': bool(filters),
            'sort_applied': bool(sort_config)
        })
        
    except Exception as e:
        logger.error(f"خطا در اعمال فیلتر به بارنامه‌ها: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در اعمال فیلتر: {str(e)}'
        }, status=500)

@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["POST"])
def get_barnameh_column_values(request):
    """
    API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر
    """
    logger.warning(f"API برای دریافت مقادیر منحصر به فرد ستون بارنامه توسط {request.user.username}. {get_client_ip(request)}")
    try:
        column_id = request.POST.get('column_id')
        search_term = request.POST.get('search', '')
        # دریافت فیلترهای فعلی
        current_filters = request.POST.get('current_filters', '{}')
        # دریافت جستجوی سریع
        global_search = request.POST.get('global_search', '')
        
        try:
            current_filters = json.loads(current_filters) if current_filters else {}
        except (json.JSONDecodeError, TypeError):
            current_filters = {}
        
        if not column_id:
            return JsonResponse({
                'status': 'error',
                'message': 'شناسه ستون ارسال نشده است'
            }, status=400)
        
        # ایجاد QuerySet پایه
        base_queryset = Barnameh.objects.select_related(
            'purchase', 'shenase_takhsis', 'purchase__cargo', 'purchase__cargo__vared_konandeh'
        )
        
        # اعمال فیلترهای فعلی (بجز فیلتر ستون فعلی)
        if current_filters:
            filter_conditions = Q()
            
            for filter_column_id, filter_data in current_filters.items():
                # رد کردن فیلتر ستون فعلی
                if filter_column_id == column_id:
                    continue
                    
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if filter_column_id == 'number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(number__in=values)
                        else:
                            filter_conditions &= ~Q(number__in=values)
                        
                elif filter_column_id == 'serial':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(serial__in=values)
                        else:
                            filter_conditions &= ~Q(serial__in=values)
                        
                elif filter_column_id == 'purchase_number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(purchase_number__in=values)
                        
                elif filter_column_id == 'status':
                    # تبدیل نمایش وضعیت به کد وضعیت
                    status_map = {
                        'بارنامه ناقص': 'BARNAMEH_INCOMPLETE',
                        'بارنامه کامل': 'BARNAMEH_COMPLETE',
                        'ارسال شده به بازارگاه': 'PURCHASE_CLOSED'
                    }
                    status_codes = []
                    for v in values:
                        if v in status_map:
                            status_codes.append(status_map[v])
                        else:
                            status_codes.append(v)
                    
                    if status_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(status__in=status_codes)
                        else:
                            filter_conditions &= ~Q(status__in=status_codes)
                        
                elif filter_column_id == 'cargo':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__cargo__cottage__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__cargo__cottage__in=values)
                
                elif filter_column_id in ['driver_name', 'driver_phone', 'vehicle_plate', 
                                        'receiver_name', 'destination', 'shenase_takhsis_code']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{filter_column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{filter_column_id}__in': values})
                
                elif filter_column_id == 'tonnage':
                    # فیلتر عددی
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        if numeric_values:
                            if filter_type == 'include':
                                filter_conditions &= Q(tonnage__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(tonnage__in=numeric_values)
                                
                    except (ValueError, TypeError):
                        continue
                        
                elif filter_column_id == 'barnameh_date':
                    # فیلتر تاریخی
                    try:
                        date_conditions = Q()
                        for date_str in values:
                            if date_str and date_str.strip():
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts) == 3:
                                        year, month, day = parts
                                        date_obj = datetime(int(year), int(month), int(day)).date()
                                        date_conditions |= Q(barnameh_date=date_obj)
                        
                        if date_conditions:
                            if filter_type == 'include':
                                filter_conditions &= date_conditions
                            else:
                                filter_conditions &= ~date_conditions
                                
                    except (ValueError, TypeError):
                        continue
                
                elif filter_column_id in ['is_sent_to_bki', 'is_factored', 'is_created_by_excel']:
                    bool_values = []
                    for v in values:
                        if v in ['بله', 'فعال', True, 'true', '1']:
                            bool_values.append(True)
                        elif v in ['خیر', 'غیرفعال', False, 'false', '0']:
                            bool_values.append(False)
                    
                    if bool_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{filter_column_id}__in': bool_values})
                        else:
                            filter_conditions &= ~Q(**{f'{filter_column_id}__in': bool_values})
            
            # اعمال فیلترها
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # استخراج مقادیر بر اساس نوع ستون
        values = set()
        
        if column_id == 'number':
            values_queryset = base_queryset.exclude(number__isnull=True)\
                .exclude(number='').values_list('number', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'serial':
            values_queryset = base_queryset.exclude(serial__isnull=True)\
                .exclude(serial='').values_list('serial', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'purchase_number':
            values_queryset = base_queryset.exclude(purchase_number__isnull=True)\
                .exclude(purchase_number='').values_list('purchase_number', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'status':
            values_queryset = base_queryset.values_list('status', flat=True).distinct()
            # تبدیل کدهای وضعیت به نمایش فارسی
            status_choices = {
                'BARNAMEH_INCOMPLETE': 'بارنامه ناقص',
                'BARNAMEH_COMPLETE': 'بارنامه کامل',
                'PURCHASE_CLOSED': 'ارسال شده به بازارگاه'
            }
            values = set([status_choices.get(state, state) for state in values_queryset if state])
            
        elif column_id == 'cargo':
            values_queryset = base_queryset.exclude(purchase__cargo__isnull=True)\
                .values_list('purchase__cargo__cottage', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id in ['driver_name', 'driver_phone', 'vehicle_plate', 
                          'receiver_name', 'destination', 'shenase_takhsis_code']:
            values_queryset = base_queryset.exclude(**{f'{column_id}__isnull': True})\
                .exclude(**{f'{column_id}': ''}).values_list(column_id, flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'tonnage':
            values_queryset = base_queryset.exclude(tonnage__isnull=True)\
                .exclude(tonnage=0)\
                .values_list('tonnage', flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'barnameh_date':
            values_queryset = base_queryset.exclude(barnameh_date__isnull=True)\
                .values_list('barnameh_date', flat=True).distinct()
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])
            
        elif column_id in ['is_sent_to_bki', 'is_factored', 'is_created_by_excel']:
            field_values = base_queryset.values_list(column_id, flat=True).distinct()
            values = set()
            for val in field_values:
                if val is True:
                    values.add('بله')
                elif val is False:
                    values.add('خیر')
        
        else:
            # برای ستون‌های ناشناخته
            values = set()
        
        # تبدیل به لیست و مرتب‌سازی
        values_list = sorted(list(values), key=lambda x: str(x).lower())
        
        # حذف مقادیر خالی و نامعتبر
        values_list = [v for v in values_list if v and str(v).strip() and str(v) != 'None']
        
        # اعمال جستجو اگر ارسال شده باشد
        if search_term:
            search_lower = search_term.lower()
            values_list = [v for v in values_list if search_lower in str(v).lower()]
        
        return JsonResponse({
            'status': 'success',
            'values': values_list
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Error in get_barnameh_column_values: {str(e)} , {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': "خطا در دریافت مقادیر ستون"
        }, status=500)

@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["GET"])
def barnameh_column_values(request, column_id):
    """Get unique values for a specific column in barnameh table using table_filter system"""
    try:
        # Check if column_id is 'dummy', which is used as a placeholder in the URL pattern
        if column_id == 'dummy':
            # Get actual column_id from query parameters
            column_id = request.GET.get('column_id')
            if not column_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No column_id provided'
                }, status=400)
                
        logger.warning(f"درخواست مقادیر ستون {column_id} توسط {request.user.username}. {get_client_ip(request)}")
        
        # Get current filters to respect them when showing values
        current_filters = request.GET.get('current_filters')
        if current_filters:
            try:
                current_filters = json.loads(current_filters)
                # Remove filter for current column to avoid circular filtering
                current_filters.pop(column_id, None)
            except json.JSONDecodeError:
                current_filters = {}
        else:
            current_filters = {}
        
        # Create base queryset with related entities
        queryset = Barnameh.objects.all().select_related('purchase', 'shenase_takhsis', 'purchase__cargo', 'purchase__cargo__vared_konandeh')
        
        # Apply current filters
        if current_filters:
            from table_filter.utils import TableFilterProcessor
            processor = TableFilterProcessor(queryset, 'barnameh')
            queryset = processor.apply_filters(current_filters)
            
        # Get column values
        processor = TableFilterProcessor(queryset, 'barnameh')
        column_values = processor.get_column_values(column_id, limit=500)
        
        return JsonResponse({
            'status': 'success',
            'values': column_values,
            'total_count': len(column_values)
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت مقادیر ستون {column_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت مقادیر ستون: {str(e)}'
        }, status=500)

def update_barnameh(barnameh_id, data):
    """
    Update a Barnameh object with new data
    
    Args:
        barnameh_id: ID of the Barnameh object to update
        data: Dictionary containing the fields to update
    
    Returns:
        dict: Result of the update operation
    """
    try:
        barnameh = Barnameh.objects.get(id=barnameh_id)
        
        # Check if barnameh is already sent to BKI
        if barnameh.is_sent_to_bki and not data.get('force_update', False):
            return {
                'success': False,
                'message': 'این بارنامه قبلاً به بازارگاه ارسال شده است و قابل ویرایش نیست.'
            }
        
        # Update fields
        if 'number' in data:
            barnameh.number = data['number']
        
        if 'serial' in data:
            barnameh.serial = data['serial']
        
        if 'tonnage' in data:
            barnameh.tonnage = data['tonnage']
        
        if 'driver_phone' in data:
            barnameh.driver_phone = data['driver_phone']
        
        if 'driver_name' in data:
            barnameh.driver_name = data['driver_name']
        
        if 'vehicle_plate' in data:
            barnameh.vehicle_plate = data['vehicle_plate']
        
        if 'receiver_name' in data:
            barnameh.receiver_name = data['receiver_name']
        
        if 'destination' in data:
            barnameh.destination = data['destination']
        
        if 'barnameh_date' in data:
            try:
                if isinstance(data['barnameh_date'], str):
                    # Assuming format is like '1402/01/01'
                    parts = data['barnameh_date'].split('/')
                    if len(parts) == 3:
                        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                        barnameh.barnameh_date = jdatetime.date(year, month, day)
                else:
                    barnameh.barnameh_date = data['barnameh_date']
            except Exception as e:
                logger.error(f"خطا در تبدیل تاریخ: {str(e)}")
                return {
                    'success': False,
                    'message': f'خطا در تبدیل تاریخ: {str(e)}'
                }
        
        if 'purchase_number' in data:
            barnameh.purchase_number = data['purchase_number']
        
        if 'shenase_takhsis_code' in data:
            barnameh.shenase_takhsis_code = data['shenase_takhsis_code']
        
        # Check if barnameh is complete
        if all([barnameh.number, barnameh.serial, barnameh.tonnage]):
            barnameh.status = 'BARNAMEH_COMPLETE'
        else:
            barnameh.status = 'BARNAMEH_INCOMPLETE'
        
        barnameh.save()
        
        
        return {
            'success': True,
            'message': 'بارنامه با موفقیت بروزرسانی شد.',
            'barnameh': barnameh
        }
        
    except Barnameh.DoesNotExist:
        logger.error(f"بارنامه مورد نظر یافت نشد.")
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        logger.error(f"خطا در بروزرسانی بارنامه: {str(e)}")
        return {
            'success': False,
            'message': f'خطا در بروزرسانی بارنامه: {str(e)}'
        }

def delete_barnameh(barnameh_id):
    """
    Delete a Barnameh object
    
    Args:
        barnameh_id: ID of the Barnameh object to delete
    
    Returns:
        dict: Result of the delete operation
    """
    try:
        barnameh = Barnameh.objects.get(id=barnameh_id)
        
        # Check if barnameh is already sent to BKI
        if barnameh.is_sent_to_bki:
            logger.error(f"بارنامه {barnameh_id} قبلاً به بازارگاه ارسال شده است و قابل حذف نیست.")
            return {
                'success': False,
                'message': 'این بارنامه قبلاً به بازارگاه ارسال شده است و قابل حذف نیست.'
            }
        
        barnameh.delete()
        
        return {
            'success': True,
            'message': 'بارنامه با موفقیت حذف شد.'
        }
        
    except Barnameh.DoesNotExist:
        logger.error(f"بارنامه {barnameh_id} یافت نشد.")
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        logger.error(f"خطا در حذف بارنامه: {str(e)}")
        return {
            'success': False,
            'message': f'خطا در حذف بارنامه: {str(e)}'
        }

@role_required('logistics_manager', 'admin', 'financial_manager')
def barnameh_list(request):
    """
    نمایش لیست بارنامه ها با فیلتر server-side
    """
    logger.warning(f"لیست بارنامه ها: {get_client_ip(request)}, user: {request.user}")
    
    # دریافت ستون‌های انتخاب شده
    selected_columns = get_barnameh_columns_from_cookie(request)
    all_columns = get_all_barnameh_columns()
    
    # دریافت پارامترهای فیلتر از GET
    global_search = request.GET.get('global_search', '')
    page = int(request.GET.get('page', 1))
    per_page_param = request.GET.get('per_page', 50)
    
    # بررسی گزینه "نمایش همه"
    if per_page_param == 'all':
        per_page = 10000  # عدد بزرگ برای نمایش همه
    else:
        try:
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            per_page = 50
    
    # بررسی اینکه آیا درخواست AJAX است
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # فیلدهای ضروری برای QuerySet
    selected_fields = [
        'id', 'number', 'serial', 'tonnage', 'status', 'driver_name', 
        'driver_phone', 'vehicle_plate', 'receiver_name', 'destination', 
        'barnameh_date', 'transport_date', 'purchase_number', 'shenase_takhsis_code',
        'is_sent_to_bki', 'barnameh_created_at', 'factor_sodoor_season', 
        'is_factored', 'is_created_by_excel', 'buyer_postal_code',
        'is_sent_to_bki_at', 'is_created_by_excel_at', 'barnameh_updated_at'
    ]
    
    # فیلدهای related
    purchase_fields = ['purchase__id', 'purchase__cargo__cottage', 'purchase__cargo__product_type', 
                      'purchase__cargo__company_price', 'purchase__cargo__customer_price',
                      'purchase__cargo__vared_konandeh__name', 'purchase__demand_amount']
    shenase_fields = ['shenase_takhsis__id', 'shenase_takhsis__code']
    
    all_fields = selected_fields + purchase_fields + shenase_fields
    
    # ایجاد QuerySet پایه
    base_queryset = Barnameh.objects.select_related(
        'purchase', 'shenase_takhsis', 'purchase__cargo', 'purchase__cargo__vared_konandeh'
    ).order_by('-barnameh_created_at')
    
    # اعمال فیلترهای پایه
    filters = Q()
    
    # فیلتر جستجوی سریع
    if global_search:
        search_filters = (
            Q(number__icontains=global_search) |
            Q(serial__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(shenase_takhsis_code__icontains=global_search) |
            Q(driver_name__icontains=global_search) |
            Q(driver_phone__icontains=global_search) |
            Q(vehicle_plate__icontains=global_search) |
            Q(receiver_name__icontains=global_search) |
            Q(destination__icontains=global_search) |
            Q(purchase__cargo__cottage__icontains=global_search) |
            Q(purchase__cargo__vared_konandeh__name__icontains=global_search)
        )
        filters &= search_filters
    
    # اعمال فیلترها
    if filters:
        barnamehs = base_queryset.filter(filters)
    else:
        barnamehs = base_queryset
    
    # صفحه‌بندی
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(barnamehs, per_page)
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
        page = 1
    
    # اگر درخواست AJAX است، فقط داده‌های JSON برگردان
    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'data': {
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'number': page_obj.number,
                'num_pages': paginator.num_pages,
                'count': paginator.count,
                'page_range': list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)),
            }
        })
    
    context = {
        'barnamehs': page_obj,
        'all_columns': all_columns,
        'selected_columns': selected_columns,
        'paginator': paginator,
        'page_obj': page_obj,
        'current_page': page,
        'per_page': per_page_param,
        'total_count': paginator.count,
        'page_range': list(paginator.get_elided_page_range(page, on_each_side=2, on_ends=1)),
        'search_params': {
            'global_search': global_search,
            'per_page': per_page_param,
        },
    }
    
    return render(request, 'bki_barnameh/barnameh_list.html', context)

@role_required('logistics_manager', 'admin')
def barnameh_detail(request, barnameh_id):
    """
    نمایش جزئیات بارنامه
    """
    logger.warning(f"جزئیات بارنامه: {barnameh_id}, ip: {get_client_ip(request)}, user: {request.user}")
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/barnameh_detail.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def barnameh_create(request):
    """
    ایجاد بارنامه جدید
    """
    logger.warning(f"ایجاد بارنامه جدید: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        data = {
            'number': request.POST.get('number'),
            'serial': request.POST.get('serial'),
            'tonnage': request.POST.get('tonnage'),
            'driver_phone': request.POST.get('driver_phone'),
            'driver_name': request.POST.get('driver_name'),
            'vehicle_plate': request.POST.get('vehicle_plate'),
            'receiver_name': request.POST.get('receiver_name'),
            'destination': request.POST.get('destination'),
            'barnameh_date': request.POST.get('barnameh_date'),
            'purchase_number': request.POST.get('purchase_number'),
            'shenase_takhsis_code': request.POST.get('shenase_takhsis_code'),
        }
        
        barnameh = Barnameh.objects.create(
            number=data['number'],
            serial=data['serial'],
            tonnage=data['tonnage'] if data['tonnage'] else None,
            driver_phone=data['driver_phone'],
            driver_name=data['driver_name'],
            vehicle_plate=data['vehicle_plate'],
            receiver_name=data['receiver_name'],
            destination=data['destination'],
            barnameh_date=data['barnameh_date'] if data['barnameh_date'] else None,
            purchase_number=data['purchase_number'],
            shenase_takhsis_code=data['shenase_takhsis_code'],
            status='BARNAMEH_COMPLETE' if all([data['number'], data['serial'], data['tonnage']]) else 'BARNAMEH_INCOMPLETE'
        )
        
        messages.success(request, 'بارنامه با موفقیت ایجاد شد.')
        return redirect('barnameh_detail', barnameh_id=barnameh.id)
    
    return render(request, 'bki_barnameh/barnameh_create.html')

@role_required('logistics_manager', 'admin')
def barnameh_edit(request, barnameh_id):
    """
    ویرایش بارنامه
    """
    logger.warning(f"ویرایش بارنامه: {barnameh_id}, ip: {get_client_ip(request)}, user: {request.user}")
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    
    if request.method == 'POST':
        data = {
            'number': request.POST.get('number'),
            'serial': request.POST.get('serial'),
            'tonnage': request.POST.get('tonnage'),
            'driver_phone': request.POST.get('driver_phone'),
            'driver_name': request.POST.get('driver_name'),
            'vehicle_plate': request.POST.get('vehicle_plate'),
            'receiver_name': request.POST.get('receiver_name'),
            'destination': request.POST.get('destination'),
            'barnameh_date': request.POST.get('barnameh_date'),
            'purchase_number': request.POST.get('purchase_number'),
            'shenase_takhsis_code': request.POST.get('shenase_takhsis_code'),
        }
        
        result = update_barnameh(barnameh_id, data)
        barnameh.log_barnameh_edit(request)
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('barnameh_detail', barnameh_id=barnameh.id)
        else:
            messages.error(request, result['message'])
    
    return render(request, 'bki_barnameh/barnameh_edit.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def barnameh_delete(request, barnameh_id):
    """
    حذف بارنامه
    """
    logger.warning(f"حذف بارنامه: {barnameh_id}, ip: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        result = delete_barnameh(barnameh_id)
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('barnameh_list')
        else:
            messages.error(request, result['message'])
            return redirect('barnameh_detail', barnameh_id=barnameh_id)
    
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/barnameh_delete.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def upload_excel(request):
    """
    آپلود فایل اکسل بارنامه - ریدایرکت به ویو جدید
    """
    logger.warning(f"آپلود فایل اکسل بارنامه: {get_client_ip(request)}, user: {request.user}")
    return upload_excel_view(request)

@role_required('logistics_manager', 'admin', 'financial_manager')
def export_excel(request):
    """
    خروجی اکسل از بارنامه‌ها
    """
    logger.warning(f"خروجی اکسل از بارنامه‌ها: {get_client_ip(request)}, user: {request.user}")
    return export_excel_view(request)

@role_required('logistics_manager', 'admin')
def send_to_bki(request, barnameh_id):
    """
    ارسال بارنامه به بازارگاه
    """
    logger.warning(f"ارسال بارنامه به بازارگاه: {barnameh_id}, ip: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        result = send_barnameh_to_bki(barnameh_id)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        return redirect('barnameh_detail', barnameh_id=barnameh_id)
    
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/send_to_bki.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def bulk_send_to_bki(request):
    """
    ارسال گروهی بارنامه‌ها به بازارگاه
    """
    logger.warning(f"ارسال گروهی بارنامه‌ها به بازارگاه: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        
        if not barnameh_ids:
            messages.error(request, 'هیچ بارنامه‌ای انتخاب نشده است.')
            return redirect('barnameh_list')
        
        result = send_multiple_barnameh_to_bki(barnameh_ids)
        
        if result['success'] > 0:
            messages.success(request, f"{result['success']} بارنامه با موفقیت به بازارگاه ارسال شد.")
        
        if result['failed'] > 0:
            messages.error(request, f"{result['failed']} بارنامه با خطا مواجه شد.")
            for message in result['messages']:
                messages.error(request, message)
        
        return redirect('barnameh_list')
    
    return redirect('barnameh_list')

@csrf_exempt
@role_required('logistics_manager', 'admin')
def barnameh_api(request):
    """
    API برای مدیریت بارنامه‌ها
    """
    logger.warning(f"API برای مدیریت بارنامه‌ها: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'GET':
        barnameh_id = request.GET.get('id')
        
        if barnameh_id:
            try:
                barnameh = Barnameh.objects.get(id=barnameh_id)
                data = {
                    'id': barnameh.id,
                    'number': barnameh.number,
                    'serial': barnameh.serial,
                    'tonnage': float(barnameh.tonnage) if barnameh.tonnage else None,
                    'driver_phone': barnameh.driver_phone,
                    'driver_name': barnameh.driver_name,
                    'vehicle_plate': barnameh.vehicle_plate,
                    'receiver_name': barnameh.receiver_name,
                    'destination': barnameh.destination,
                    'barnameh_date': str(barnameh.barnameh_date) if barnameh.barnameh_date else None,
                    'purchase_number': barnameh.purchase_number,
                    'shenase_takhsis_code': barnameh.shenase_takhsis_code,
                    'status': barnameh.status,
                    'is_sent_to_bki': barnameh.is_sent_to_bki,
                }
                return JsonResponse({'success': True, 'data': data})
            except Barnameh.DoesNotExist:
                logger.error(f"بارنامه {barnameh_id} یافت نشد.")
                return JsonResponse({'success': False, 'message': 'بارنامه مورد نظر یافت نشد.'})
        else:
            barnamehs = Barnameh.objects.all().order_by('-barnameh_created_at')
            data = []
            for barnameh in barnamehs:
                data.append({
                    'id': barnameh.id,
                    'number': barnameh.number,
                    'serial': barnameh.serial,
                    'tonnage': float(barnameh.tonnage) if barnameh.tonnage else None,
                    'status': barnameh.status,
                    'is_sent_to_bki': barnameh.is_sent_to_bki,
                })
            return JsonResponse({'success': True, 'data': data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            barnameh_id = data.get('id')
            
            if barnameh_id:
                # Update existing barnameh
                result = update_barnameh(barnameh_id, data)
            else:
                # Create new barnameh
                barnameh = Barnameh.objects.create(
                    number=data.get('number'),
                    serial=data.get('serial'),
                    tonnage=data.get('tonnage'),
                    driver_phone=data.get('driver_phone'),
                    driver_name=data.get('driver_name'),
                    vehicle_plate=data.get('vehicle_plate'),
                    receiver_name=data.get('receiver_name'),
                    destination=data.get('destination'),
                    barnameh_date=data.get('barnameh_date'),
                    purchase_number=data.get('purchase_number'),
                    shenase_takhsis_code=data.get('shenase_takhsis_code'),
                    status='BARNAMEH_COMPLETE' if all([data.get('number'), data.get('serial'), data.get('tonnage')]) else 'BARNAMEH_INCOMPLETE'
                )
                result = {
                    'success': True,
                    'message': 'بارنامه با موفقیت ایجاد شد.',
                    'barnameh': barnameh
                }
            
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'خطا: {str(e)}'})
    
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            barnameh_id = data.get('id')
            
            if not barnameh_id:
                logger.error('شناسه بارنامه مشخص نشده است.')
                return JsonResponse({'success': False, 'message': 'شناسه بارنامه مشخص نشده است.'})
            
            result = delete_barnameh(barnameh_id)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f'خطا در حذف بارنامه: {str(e)}')
            return JsonResponse({'success': False, 'message': f'خطا: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'درخواست نامعتبر است.'})

@role_required('logistics_manager', 'admin')
def edit_barnameh_in_bki(request, barnameh_id):
    """
    ویرایش بارنامه در بازارگاه
    """
    logger.warning(f"ویرایش بارنامه در بازارگاه: {barnameh_id}, ip: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        result = edit_barnameh_api(barnameh_id)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        return redirect('barnameh_detail', barnameh_id=barnameh_id)
    
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/edit_barnameh_in_bki.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def bulk_edit(request):
    """
    ویرایش گروهی بارنامه‌ها
    """
    logger.warning(f"ویرایش گروهی بارنامه‌ها: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        
        if not barnameh_ids:
            messages.error(request, 'هیچ بارنامه‌ای انتخاب نشده است.')
            return redirect('barnameh_list')
        
        # دریافت بارنامه‌های انتخاب شده
        barnamehs = Barnameh.objects.filter(id__in=barnameh_ids)
        
        # اگر فرم ویرایش ارسال شده باشد
        if 'save_changes' in request.POST:
            field_to_update = request.POST.get('field_to_update')
            new_value = request.POST.get('new_value')
            
            if not field_to_update or not new_value:
                messages.error(request, 'لطفاً فیلد و مقدار جدید را وارد کنید.')
                return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
            
            # بررسی معتبر بودن فیلد
            valid_fields = ['tonnage', 'driver_name', 'driver_phone', 'vehicle_plate', 
                           'receiver_name', 'destination', 'barnameh_date']
            
            if field_to_update not in valid_fields:
                messages.error(request, 'فیلد انتخاب شده معتبر نیست.')
                return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
            
            # اعمال تغییرات برای همه بارنامه‌های انتخاب شده
            success_count = 0
            error_count = 0
            error_messages = []
            success_details = []
            error_details = []
            
            for barnameh in barnamehs:
                # اگر بارنامه به بازارگاه ارسال نشده باشد
                if not barnameh.is_sent_to_bki:
                    try:
                        # پردازش مقدار بر اساس نوع فیلد
                        processed_value = new_value
                        
                        if field_to_update == 'tonnage':
                            try:
                                processed_value = float(new_value)
                            except ValueError:
                                error_count += 1
                                error_message = f'مقدار وارد شده برای وزن معتبر نیست: {new_value}'
                                error_messages.append(error_message)
                                error_details.append({
                                    'id': barnameh.id,
                                    'number': barnameh.number,
                                    'serial': barnameh.serial,
                                    'error': error_message
                                })
                                logger.error(f"مقدار وارد شده برای وزن معتبر نیست: {new_value}")
                                continue
                        
                        elif field_to_update == 'barnameh_date':
                            try:
                                # تبدیل تاریخ شمسی به فرمت مناسب
                                parts = new_value.split('/')
                                if len(parts) == 3:
                                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                                    processed_value = jdatetime.date(year, month, day)
                                else:
                                    error_count += 1
                                    error_message = f'فرمت تاریخ معتبر نیست: {new_value}. از فرمت 1402/01/01 استفاده کنید.'
                                    error_messages.append(error_message)
                                    error_details.append({
                                        'id': barnameh.id,
                                        'number': barnameh.number,
                                        'serial': barnameh.serial,
                                        'error': error_message
                                    })
                                    logger.error(f"فرمت تاریخ معتبر نیست: {new_value}. از فرمت 1402/01/01 استفاده کنید.")
                                    continue
                            except Exception as e:
                                error_count += 1
                                error_message = f'خطا در تبدیل تاریخ: {str(e)}'
                                error_messages.append(error_message)
                                error_details.append({
                                    'id': barnameh.id,
                                    'number': barnameh.number,
                                    'serial': barnameh.serial,
                                    'error': error_message
                                })
                                logger.error(f"خطا در تبدیل تاریخ: {str(e)}")
                                continue
                        
                        # بروزرسانی فیلد مورد نظر
                        setattr(barnameh, field_to_update, processed_value)
                        barnameh.save()
                        success_count += 1
                        
                        # اضافه کردن به لیست موفق‌ها
                        success_details.append({
                            'id': barnameh.id,
                            'number': barnameh.number,
                            'serial': barnameh.serial
                        })
                        
                        # ایجاد لاگ برای ویرایش
                        from django.utils import timezone
                        barnameh.barnameh_logs.create(
                            log_message=f"ویرایش گروهی: فیلد '{field_to_update}' به مقدار '{new_value}' تغییر کرد",
                            log_date=timezone.now()
                        )
                    except Exception as e:
                        error_count += 1
                        error_message = f'خطا در بروزرسانی بارنامه {barnameh.number}/{barnameh.serial}: {str(e)}'
                        error_messages.append(error_message)
                        error_details.append({
                            'id': barnameh.id,
                            'number': barnameh.number,
                            'serial': barnameh.serial,
                            'error': error_message
                        })
                        logger.error(f"خطا در بروزرسانی بارنامه {barnameh.number}/{barnameh.serial}: {str(e)}")
                else:
                    error_count += 1
                    error_message = f'بارنامه {barnameh.number}/{barnameh.serial} قبلاً به بازارگاه ارسال شده است و قابل ویرایش نیست.'
                    error_messages.append(error_message)
                    error_details.append({
                        'id': barnameh.id,
                        'number': barnameh.number,
                        'serial': barnameh.serial,
                        'error': error_message
                    })
                    logger.error(f"بارنامه {barnameh.number}/{barnameh.serial} قبلاً به بازارگاه ارسال شده است و قابل ویرایش نیست.")
            # ذخیره نتایج در سشن برای نمایش در صفحه نتایج
            request.session['bulk_edit_results'] = {
                'field': field_to_update,
                'value': new_value,
                'success_count': success_count,
                'error_count': error_count,
                'success_details': success_details,
                'error_details': error_details[:10]  # حداکثر 10 خطا را ذخیره می‌کنیم
            }
            
            if success_count > 0:
                messages.success(request, f'{success_count} بارنامه با موفقیت بروزرسانی شد.')
            
            if error_count > 0:
                messages.error(request, f'{error_count} بارنامه با خطا مواجه شد.')
                for error in error_messages[:5]:  # نمایش حداکثر 5 پیام خطا
                    messages.error(request, error)
                
                if len(error_messages) > 5:
                    messages.error(request, f'و {len(error_messages) - 5} خطای دیگر...')
            
            return redirect('barnameh_list')
        
        return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
    
    return redirect('barnameh_list')

@role_required('logistics_manager', 'admin')
def estelame_barnameh_view(request, barnameh_id):
    """
    استعلام بارنامه از بازارگاه
    """
    logger.warning(f"استعلام بارنامه از بازارگاه: {barnameh_id}, ip: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        # Get date parameters from request
        from_date = request.POST.get('from_date', None)
        to_date = request.POST.get('to_date', None)
        
        # Call API function
        result = estelame_barnameh(barnameh_id, from_date, to_date)
        
        if result['success']:
            messages.success(request, 'استعلام بارنامه با موفقیت انجام شد.')
            # Pass data to template
            barnameh = get_object_or_404(Barnameh, id=barnameh_id)
            return render(request, 'bki_barnameh/barnameh_estelam.html', {
                'barnameh': barnameh,
                'estelam_data': result['data']
            })
        else:
            messages.error(request, result['message'])
            return redirect('barnameh_detail', barnameh_id=barnameh_id)
    else:
        return redirect('barnameh_detail', barnameh_id=barnameh_id)

@role_required('logistics_manager', 'admin')
def bulk_delete(request):
    """
    حذف گروهی بارنامه‌ها
    """
    logger.warning(f"حذف گروهی بارنامه‌ها: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        
        if not barnameh_ids:
            messages.error(request, 'هیچ بارنامه‌ای انتخاب نشده است.')
            return redirect('barnameh_list')
        
        success_count = 0
        error_count = 0
        
        for barnameh_id in barnameh_ids:
            try:
                barnameh = Barnameh.objects.get(id=barnameh_id)
                # فقط بارنامه‌هایی که به بازارگاه ارسال نشده‌اند را حذف می‌کنیم
                if not barnameh.is_sent_to_bki:
                    barnameh.delete()
                    success_count += 1
                else:
                    error_count += 1
            except Barnameh.DoesNotExist:
                error_count += 1
                continue
        
        if success_count > 0:
            messages.success(request, f'{success_count} بارنامه با موفقیت حذف شد.')
        if error_count > 0:
            messages.error(request, f'{error_count} بارنامه به دلیل ارسال به بازارگاه یا خطای دیگر حذف نشد.')
        
        return redirect('barnameh_list')
    
    return redirect('barnameh_list')

@role_required('logistics_manager', 'admin', 'financial_manager')
def export_barnameh_excel(request):
    """
    خروجی اکسل از بارنامه‌های انتخاب شده
    """
    logger.warning(f"خروجی اکسل بارنامه‌ها توسط {request.user.username} با متد {request.method} و آی‌پی {get_client_ip(request)} آغاز شد")
    
    # پشتیبانی از درخواست‌های GET و POST
    if request.method == 'POST':
        barnameh_ids = request.POST.get('ids', '').split(',')
        selected_columns = request.POST.get('columns', '')
    else:
        barnameh_ids = request.GET.get('ids', '').split(',')
        selected_columns = request.GET.get('columns', '')
    
    logger.warning(f"raw select columns for user {request.user.username}: {selected_columns}")
    
    if selected_columns:
        # حذف کوتیشن‌های اضافی و decode کردن کاراکترهای escape شده
        selected_columns = selected_columns.strip('"').replace('\\054', ',').replace('\\\\', '\\')
        selected_columns = selected_columns.split(',')
        # حذف فیلدهای خالی
        selected_columns = [col.strip() for col in selected_columns if col.strip()]
    else:
        selected_columns = ['number', 'serial', 'tonnage', 'status', 'driver_name', 'barnameh_date']
    
    # فیلتر کردن آیدی‌های خالی
    barnameh_ids = [bid.strip() for bid in barnameh_ids if bid.strip()]

    if not barnameh_ids:
        logger.warning("ERROR: No barnameh IDs to export excel!")
        return JsonResponse({'status': 'error', 'message': 'هیچ بارنامه‌ای انتخاب نشده است'}, status=400)
    
    # بررسی تعداد بارنامه‌ها
    total_count = len(barnameh_ids)
    logger.warning(f"Total barnamehs to export: {total_count}")
    
    try:
        return _export_barnameh_excel(barnameh_ids, selected_columns)
            
    except Exception as e:
        # لاگ خطا
        import traceback
        logger.warning(f"Error in export_barnameh_excel: {str(e)}, {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد فایل اکسل'}, status=500)

def _export_barnameh_excel(barnameh_ids, selected_columns):
    """پردازش و ایجاد فایل اکسل برای بارنامه‌ها"""
    barnamehs = Barnameh.objects.filter(id__in=barnameh_ids).order_by('-barnameh_created_at')
    
    logger.warning(f"Found {barnamehs.count()} barnamehs")
    
    if barnamehs.count() == 0:
        logger.warning("ERROR: No barnamehs found!")
        return JsonResponse({'status': 'error', 'message': 'هیچ بارنامه‌ای با شناسه‌های داده شده یافت نشد'}, status=400)
    
    wb = Workbook()
    ws = wb.active
    ws.title = "لیست بارنامه‌ها"
    
    # تنظیم گردش متن از راست به چپ برای کل صفحه
    ws.sheet_view.rightToLeft = True
    
    # تعریف استایل‌ها
    header_font = Font(name='B Nazanin', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='38A169', end_color='38A169', fill_type='solid')  # سبز مطابق طرح
    
    # تنظیم راست چین و وسط چین
    alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
    
    # تعریف خطوط جدول
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # مپینگ کامل ستون‌ها به فیلدهای مدل بارنامه
    column_mapping = {
        'number': ('شماره بارنامه', lambda b: b.number or "تعیین نشده"),
        'serial': ('سریال', lambda b: b.serial or "تعیین نشده"),
        'tonnage': ('وزن (کیلوگرم)', lambda b: f"{b.tonnage}" if b.tonnage else "0"),
        'status': ('وضعیت', lambda b: b.get_status_display() if b.status else "-"),
        'driver_name': ('نام راننده', lambda b: b.driver_name or "-"),
        'driver_phone': ('شماره راننده', lambda b: b.driver_phone or "-"),
        'vehicle_plate': ('پلاک خودرو', lambda b: b.vehicle_plate or "-"),
        'receiver_name': ('نام گیرنده', lambda b: b.receiver_name or "-"),
        'destination': ('مقصد', lambda b: b.destination or "-"),
        'barnameh_date': ('تاریخ بارنامه', lambda b: str(b.barnameh_date) if b.barnameh_date else "-"),
        'transport_date': ('تاریخ حمل', lambda b: str(b.transport_date) if b.transport_date else "-"),
        'purchase_number': ('شماره خرید', lambda b: b.purchase_number or "-"),
        'shenase_takhsis_code': ('شناسه تخصیص', lambda b: b.shenase_takhsis_code or "-"),
        'cargo': ('کوتاژ', lambda b: str(b.get_cargo()) if b.get_cargo() else "-"),
        'company_price': ('فی خرید', lambda b: f"{b.get_company_price():,}" if b.get_company_price() else "-"),
        'customer_price': ('فی فروش', lambda b: f"{b.get_customer_price():,}" if b.get_customer_price() else "-"),
        'total_sales_amount': ('مبلغ کل فروش', lambda b: f"{b.get_total_sales_amount():,.0f}" if b.get_total_sales_amount() else "-"),
        'buyer_national_code': ('شماره ملی خریدار', lambda b: b.get_buyer_national_code() or "-"),
        'buyer_postal_code': ('کدپستی خریدار', lambda b: b.buyer_postal_code or "-"),
        'buyer_address': ('آدرس خریدار', lambda b: b.get_buyer_address() or "-"),
        'demand_amount': ('میزان تقاضا', lambda b: f"{b.get_demand_amount()}" if b.get_demand_amount() else "-"),
        'importer': ('واردکننده', lambda b: str(b.get_importer()) if b.get_importer() else "-"),
        'product_type': ('محصول', lambda b: b.get_product_type() or "-"),
        'successful_send_date': ('تاریخ ارسال موفق به بازارگاه', lambda b: str(b.get_successful_send_date()) if b.get_successful_send_date() else "-"),
        'is_sent_to_bki': ('ارسال به بازارگاه', lambda b: "بله" if b.is_sent_to_bki else "خیر"),
        'created_at': ('تاریخ ایجاد', lambda b: b.barnameh_created_at.strftime("%Y/%m/%d") if b.barnameh_created_at else "-"),
    }
    
    # فقط ستون‌های انتخاب شده را اضافه می‌کنیم
    headers = []
    for col in selected_columns:
        if col in column_mapping:
            headers.append(column_mapping[col][0])
    
    # افزودن هدرها به اکسل
    ws.append(headers)
    
    # تنظیم استایل برای سطر هدر
    for i, cell in enumerate(ws[1], 1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment
        cell.border = thin_border
    
    # داده‌ها
    row_idx = 2
    for barnameh in barnamehs:
        row = []
        for col in selected_columns:
            if col in column_mapping:
                try:
                    value = column_mapping[col][1](barnameh)
                    row.append(value)
                except Exception as e:
                    logger.warning(f"خطا در استخراج مقدار {col} برای بارنامه {barnameh.id}: {str(e)}")
                    row.append("-")
        
        ws.append(row)
        
        # تنظیم استایل برای سطرهای داده
        for j, cell in enumerate(ws[row_idx], 1):
            cell.alignment = alignment
            cell.border = thin_border
        
        row_idx += 1
    
    # تنظیم عرض ستون‌ها
    for i, column in enumerate(ws.columns, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 15
    
    # اضافه کردن فریز به سطر هدر
    ws.freeze_panes = "A2"
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"barnameh_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    logger.warning(f"Excel file created: {filename}")
    return response

