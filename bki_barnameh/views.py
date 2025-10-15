from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models.BarnamehModel import Barnameh, BarnamehLog
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
from datetime import timedelta
from persiantools.jdatetime import JalaliDateTime

logger = logging.getLogger("bki_barnameh_views")
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
import os
import io
import arabic_reshaper
from bidi.algorithm import get_display

# توابع اکسل به فولدر excel_management منتقل شده‌اند
from .excel_management.views import upload_excel_view, download_excel_template, export_excel_view

logger = logging.getLogger('bki_barnameh_views')

def persian_digits_to_english(persian_text):
    """تبدیل اعداد فارسی به انگلیسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    
    if not persian_text:
        return persian_text
    
    for persian, english in zip(persian_digits, english_digits):
        persian_text = persian_text.replace(persian, english)
    
    return persian_text

def jalali_to_gregorian_date(jalali_date_str):
    """
    تبدیل رشته تاریخ جلالی به تاریخ میلادی
    پشتیبانی از فرمت‌های مختلف: 1403/01/01، 1403-01-01، 1403.01.01
    """
    if not jalali_date_str or not isinstance(jalali_date_str, str):
        return None
    
    try:
        # تبدیل اعداد فارسی به انگلیسی
        jalali_date_str_en = persian_digits_to_english(jalali_date_str)
        
        # حذف فاصله‌ها و تبدیل جداکننده‌های مختلف به /
        jalali_date_str_en = jalali_date_str_en.strip().replace('-', '/').replace('.', '/')
        
        # تقسیم تاریخ به بخش‌های مختلف
        parts = jalali_date_str_en.split('/')
        if len(parts) != 3:
            raise ValueError("فرمت تاریخ باید به صورت YYYY/MM/DD باشد")
        
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        
        # بررسی معتبر بودن تاریخ
        if year < 1300 or year > 1500:
            raise ValueError("سال باید بین 1300 تا 1500 باشد")
        if month < 1 or month > 12:
            raise ValueError("ماه باید بین 1 تا 12 باشد")
        if day < 1 or day > 31:
            raise ValueError("روز باید بین 1 تا 31 باشد")
        
        # تبدیل تاریخ جلالی به میلادی
        jalali_date = jdatetime.date(year, month, day)
        gregorian_date = jalali_date.togregorian()
        
        return gregorian_date
        
    except ValueError as e:
        logger.error(f"خطا در تبدیل تاریخ جلالی {jalali_date_str}: {str(e)}")
        raise ValueError(f"فرمت تاریخ نامعتبر: {jalali_date_str}. {str(e)}")
    except Exception as e:
        logger.error(f"خطا در تبدیل تاریخ جلالی {jalali_date_str}: {str(e)}")
        raise ValueError(f"خطا در تبدیل تاریخ: {str(e)}")

def parse_jalali_date(date_string):
    """
    تبدیل رشته تاریخ شمسی به تاریخ جلالی
    پشتیبانی از فرمت‌های مختلف: 1402/01/01، 1402-01-01، 1402.01.01
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    # حذف فاصله‌ها و تبدیل جداکننده‌های مختلف به /
    date_string = date_string.strip().replace('-', '/').replace('.', '/')
    
    try:
        # تقسیم تاریخ به بخش‌های مختلف
        parts = date_string.split('/')
        if len(parts) != 3:
            raise ValueError("فرمت تاریخ باید به صورت YYYY/MM/DD باشد")
        
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        
        # بررسی معتبر بودن تاریخ
        if year < 1300 or year > 1500:
            raise ValueError("سال باید بین 1300 تا 1500 باشد")
        if month < 1 or month > 12:
            raise ValueError("ماه باید بین 1 تا 12 باشد")
        if day < 1 or day > 31:
            raise ValueError("روز باید بین 1 تا 31 باشد")
        
        # ایجاد تاریخ جلالی
        return jdatetime.date(year, month, day)
        
    except ValueError as e:
        raise ValueError(f"فرمت تاریخ نامعتبر: {date_string}. {str(e)}")
    except Exception as e:
        raise ValueError(f"خطا در تبدیل تاریخ: {str(e)}")

# تعریف تمام ستون‌های قابل نمایش در جدول بارنامه - ترتیب اولویت
BARNAMEH_COLUMNS = [
    {'id': 'number', 'name': 'شماره بارنامه'},
    {'id': 'serial', 'name': 'سریال بارنامه'},
    {'id': 'barnameh_date', 'name': 'تاریخ بارنامه'},
    {'id': 'driver_name', 'name': 'نام راننده'},
    {'id': 'driver_phone', 'name': 'تلفن راننده'},
    {'id': 'vehicle_plate', 'name': 'پلاک'},
    {'id': 'tonnage', 'name': 'وزن'},
    {'id': 'shenase_takhsis_code', 'name': 'شناسه تخصیص'},
    {'id': 'status', 'name': 'وضعیت'},
    {'id': 'receiver_name', 'name': 'نام تحویل گیرنده'},
    {'id': 'destination', 'name': 'آدرس تحویل'},
    {'id': 'purchase_number', 'name': 'شماره خرید'},
    {'id': 'cargo', 'name': 'کوتاژ'},
    {'id': 'company_price', 'name': 'فی خرید'},
    {'id': 'customer_price', 'name': 'فی فروش'},
    {'id': 'total_sales_amount', 'name': 'مبلغ کل فروش'},
    {'id': 'total_purchase_amount', 'name': 'مبلغ کل خرید'},
    {'id': 'buyer_name', 'name': 'نام خریدار'},
    {'id': 'buyer_national_id', 'name': 'شماره ملی خریدار'},
    {'id': 'buyer_postal_code', 'name': 'کدپستی خریدار'},
    {'id': 'buyer_address', 'name': 'آدرس خریدار'},
    {'id': 'demand_amount', 'name': 'میزان تقاضا'},
    {'id': 'importer', 'name': 'واردکننده'},
    {'id': 'product_type', 'name': 'محصول'},
    {'id': 'product_country', 'name': 'کشور محصول'},
    {'id': 'successful_send_date', 'name': 'تاریخ ارسال موفق به بازارگاه'},
    {'id': 'is_sent_to_bki', 'name': 'ارسال به بازارگاه'},
    {'id': 'created_at', 'name': 'تاریخ ایجاد'},
    {'id': 'factor_sodoor_season', 'name': 'زمان صدور فاکتور فصل'},
    {'id': 'is_factored', 'name': 'فاکتور صادر شده'},
    {'id': 'is_created_by_excel', 'name': 'ایجاد توسط اکسل'},
    {'id': 'factor_date', 'name': 'تاریخ ثبت فاکتور در سامانه مؤدیان'},
    {'id': 'is_sent_to_bki_at', 'name': 'تاریخ ارسال به بازارگاه'},
    {'id': 'is_created_by_excel_at', 'name': 'تاریخ ایجاد توسط اکسل'},
    {'id': 'barnameh_updated_at', 'name': 'تاریخ بروزرسانی'},
    {'id': 'actions', 'name': 'عملیات'},
]

# ستون‌های پیش‌فرض - ترتیب اولویت
DEFAULT_BARNAMEH_COLUMNS = [
    'number', 'serial', 'barnameh_date', 'driver_name', 'driver_phone',
    'vehicle_plate', 'tonnage', 'shenase_takhsis_code', 'status', 'actions'
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
        ).filter(type='Bazargah')
        
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
                        'ارسال نشده به بازارگاه': 'NOT_SENT_TO_BKI',
                        'ارسال شده به بازارگاه': 'SENT_TO_BKI'
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
                            # پارس تاریخ شمسی
                            if v and v.strip() and '/' in v:
                                date_obj = parse_jalali_date(v)
                                if date_obj:
                                    date_values.append(date_obj)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"خطا در پارس تاریخ {v}: {str(e)}")
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
                
                # فیلترهای مربوط به purchase
                elif column_id == 'cargo':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__cargo__cottage__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__cargo__cottage__in=values)
                
                elif column_id in ['company_price', 'customer_price', 'total_sales_amount', 'demand_amount', 'total_purchase_amount']:
                    # فیلتر عددی برای قیمت‌ها
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        if numeric_values:
                            field_mapping = {
                                'company_price': 'purchase__company_price',
                                'customer_price': 'purchase__customer_price',
                                'total_sales_amount': 'total_sales_amount',
                                'total_purchase_amount': 'total_purchase_amount',
                                'demand_amount': 'purchase__total_weight'
                            }
                            field_name = field_mapping.get(column_id)
                            if field_name:
                                if filter_type == 'include':
                                    filter_conditions &= Q(**{f'{field_name}__in': numeric_values})
                                else:
                                    filter_conditions &= ~Q(**{f'{field_name}__in': numeric_values})
                                
                    except (ValueError, TypeError):
                        continue
                
                elif column_id in ['buyer_national_id', 'buyer_address', 'buyer_name']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        field_mapping = {
                            'buyer_national_id': 'purchase__buyer_national_id',
                            'buyer_address': 'purchase__address',
                            'buyer_name': 'purchase__buyer_name'
                        }
                        field_name = field_mapping.get(column_id)
                        if field_name:
                            if filter_type == 'include':
                                filter_conditions &= Q(**{f'{field_name}__in': values})
                            else:
                                filter_conditions &= ~Q(**{f'{field_name}__in': values})
                
                elif column_id == 'importer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__cargo__vared_konandeh__name__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__cargo__vared_konandeh__name__in=values)
                
                elif column_id == 'product_type':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # تبدیل نمایش فارسی به کد محصول
                        from core.CargoProductModel import CargoProduct
                        product_choices = dict(CargoProduct.PRODUCT_TYPES)
                        reverse_product_map = {v: k for k, v in product_choices.items()}
                        product_codes = []
                        for v in values:
                            if v in reverse_product_map:
                                product_codes.append(reverse_product_map[v])
                            else:
                                product_codes.append(v)
                        
                        if product_codes:
                            if filter_type == 'include':
                                filter_conditions &= Q(purchase__cargo__product_type__in=product_codes)
                            else:
                                filter_conditions &= ~Q(purchase__cargo__product_type__in=product_codes)
                
                elif column_id == 'successful_send_date':
                    # فیلتر تاریخی شمسی
                    date_conditions = Q()
                    for date_str in values:
                        try:
                            if date_str and date_str.strip() and '/' in date_str:
                                # استفاده از تابع parse_jalali_date برای تبدیل صحیح تاریخ شمسی
                                date_obj = parse_jalali_date(date_str)
                                if date_obj:
                                    date_conditions |= Q(purchase__successful_send_date=date_obj)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"خطا در پارس تاریخ {date_str}: {str(e)}")
                            continue
                    
                    if date_conditions:
                        if filter_type == 'include':
                            filter_conditions &= date_conditions
                        else:
                            filter_conditions &= ~date_conditions
                
                elif column_id in ['factor_sodoor_season', 'buyer_postal_code']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': values})
                
                elif column_id == 'factor_date':
                    date_values = []
                    for v in values:
                        try:
                            # پارس تاریخ شمسی
                            if v and v.strip() and '/' in v:
                                date_obj = parse_jalali_date(v)
                                if date_obj:
                                    date_values.append(date_obj)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"خطا در پارس تاریخ {v}: {str(e)}")
                            continue
                    
                    if date_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(factor_date__in=date_values)
                        else:
                            filter_conditions &= ~Q(factor_date__in=date_values)

                elif column_id == 'product_country':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # تبدیل نمایش فارسی به کد کشور
                        from core.CargoProductModel import CargoProduct
                        country_choices = dict(CargoProduct.COUNTRIES)
                        reverse_country_map = {v: k for k, v in country_choices.items()}
                        country_codes = []
                        for v in values:
                            if v in reverse_country_map:
                                country_codes.append(reverse_country_map[v])
                            else:
                                country_codes.append(v)
                        
                        if country_codes:
                            if filter_type == 'include':
                                filter_conditions &= Q(purchase__cargo__country__in=country_codes)
                            else:
                                filter_conditions &= ~Q(purchase__cargo__country__in=country_codes)
                
            
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
                Q(shenase_takhsis_code__icontains=global_search) |
                Q(purchase__cargo__cottage__icontains=global_search) |
                Q(purchase__cargo__vared_konandeh__name__icontains=global_search) |
                Q(purchase__cargo__product_type__icontains=global_search) |
                Q(purchase__buyer_name__icontains=global_search) |
                Q(purchase__buyer_national_id__icontains=global_search) | # این از قبل درست بود
                Q(purchase__address__icontains=global_search) |
                Q(factor_sodoor_season__icontains=global_search) |
                Q(purchase__buyer_postal_code__icontains=global_search) | # <<< اصلاح شد
                Q(purchase__cargo__country__icontains=global_search)
            )
            base_queryset = base_queryset.filter(search_conditions)
        
        # اعمال مرتب‌سازی
        if sort_config and sort_config.get('column'):
            sort_column = sort_config['column']
            sort_direction = sort_config.get('direction', 'asc')
            
            # تعیین نام فیلد برای مرتب‌سازی بر اساس نوع ستون
            sort_field_mapping = {
                'number': 'number',
                'serial': 'serial',
                'tonnage': 'tonnage',
                'status': 'status',
                'driver_name': 'driver_name',
                'driver_phone': 'driver_phone',
                'vehicle_plate': 'vehicle_plate',
                'receiver_name': 'receiver_name',
                'destination': 'destination',
                'barnameh_date': 'barnameh_date',
                'purchase_number': 'purchase_number',
                'shenase_takhsis_code': 'shenase_takhsis_code',
                'is_sent_to_bki': 'is_sent_to_bki',
                'is_factored': 'is_factored',
                'is_created_by_excel': 'is_created_by_excel',
                'created_at': 'barnameh_created_at',
                # فیلدهای related
                'cargo': 'purchase__cargo__cottage',
                'company_price': 'purchase__company_price',
                'customer_price': 'purchase__customer_price',
                'total_sales_amount': 'total_sales_amount',
                'total_purchase_amount': 'total_purchase_amount',
                'buyer_name': 'purchase__buyer_name',
                'buyer_national_id': 'purchase__buyer_national_id',
                'buyer_address': 'purchase__address',
                'demand_amount': 'purchase__total_weight',
                'importer': 'purchase__cargo__vared_konandeh__name',
                'product_type': 'purchase__cargo__product_type',
                'successful_send_date': 'purchase__successful_send_date',
                'product_country': 'purchase__cargo__country',
            }
            
            # دریافت فیلد مرتب‌سازی
            sort_field = sort_field_mapping.get(sort_column, sort_column)
            
            if sort_direction == 'desc':
                sort_field = f'-{sort_field}'
                
            try:
                base_queryset = base_queryset.order_by(sort_field)
                logger.info(f"مرتب‌سازی اعمال شد: {sort_field}")
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
                'receiver_name': barnameh.get_delivery_receiver_name() or "",
                'destination': barnameh.get_delivery_address() or "",
                'barnameh_date': barnameh.barnameh_date.strftime("%Y/%m/%d") if barnameh.barnameh_date else "",
                'purchase_number': barnameh.purchase_number or "",
                'shenase_takhsis_code': barnameh.shenase_takhsis_code or "",
                'is_sent_to_bki': barnameh.is_sent_to_bki,
                'is_factored': barnameh.is_factored,
                'is_created_by_excel': barnameh.is_created_by_excel,
                'created_at': barnameh.barnameh_created_at.strftime("%Y/%m/%d") if hasattr(barnameh, 'barnameh_created_at') and barnameh.barnameh_created_at else "",
                'factor_sodoor_season': barnameh.factor_sodoor_season or "",
                'factor_date': barnameh.factor_date.strftime("%Y/%m/%d") if barnameh.factor_date else "",
                'buyer_postal_code': barnameh.get_buyer_postal_code() or "",
                # Related data from purchase
                'cargo': get_related_data(barnameh, 'purchase.cargo.cottage'),
                'company_price': get_related_data(barnameh, 'purchase.company_price'),
                'customer_price': get_related_data(barnameh, 'purchase.customer_price'),
                'total_sales_amount': get_related_data(barnameh, 'total_sales_amount'),
                'total_purchase_amount': get_related_data(barnameh, 'total_purchase_amount'),
                'buyer_name': barnameh.get_buyer_name() or "-",
                'buyer_national_id': barnameh.get_buyer_national_code() or "-",
                'buyer_address': get_related_data(barnameh, 'purchase.address'),
                'demand_amount': get_related_data(barnameh, 'purchase.total_weight'),
                'importer': get_related_data(barnameh, 'purchase.cargo.vared_konandeh.name'),
                'product_type': barnameh.purchase.cargo.get_product_type_display() if barnameh.purchase and barnameh.purchase.cargo and barnameh.purchase.cargo.product_type else "",
                'successful_send_date': get_related_data(barnameh, 'purchase.successful_send_date'),
                'product_country': barnameh.purchase.cargo.get_country_display() if barnameh.purchase and barnameh.purchase.cargo and barnameh.purchase.cargo.country else "",
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
        ).filter(type='Bazargah')
        
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
                        'ارسال نشده به بازارگاه': 'NOT_SENT_TO_BKI',
                        'ارسال شده به بازارگاه': 'SENT_TO_BKI'
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
                    # فیلتر تاریخی شمسی
                    date_conditions = Q()
                    for date_str in values:
                        try:
                            if date_str and date_str.strip() and '/' in date_str:
                                # استفاده از تابع parse_jalali_date برای تبدیل صحیح تاریخ شمسی
                                date_obj = parse_jalali_date(date_str)
                                if date_obj:
                                    date_conditions |= Q(barnameh_date=date_obj)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"خطا در پارس تاریخ {date_str}: {str(e)}")
                            continue
                    
                    if date_conditions:
                        if filter_type == 'include':
                            filter_conditions &= date_conditions
                        else:
                            filter_conditions &= ~date_conditions
                
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
                
                # فیلترهای مربوط به purchase
                elif filter_column_id == 'cargo':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__cargo__cottage__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__cargo__cottage__in=values)
                
                elif filter_column_id in ['company_price', 'customer_price', 'total_sales_amount', 'demand_amount', 'total_purchase_amount']:
                    # فیلتر عددی برای قیمت‌ها
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        if numeric_values:
                            field_mapping = {
                                'company_price': 'purchase__company_price',
                                'customer_price': 'purchase__customer_price',
                                'total_sales_amount': 'total_sales_amount',
                                'demand_amount': 'purchase__total_weight',
                                'total_purchase_amount': 'total_purchase_amount'
                            }
                            field_name = field_mapping.get(filter_column_id)
                            if field_name:
                                if filter_type == 'include':
                                    filter_conditions &= Q(**{f'{field_name}__in': numeric_values})
                                else:
                                    filter_conditions &= ~Q(**{f'{field_name}__in': numeric_values})
                                
                    except (ValueError, TypeError):
                        continue
                
                elif filter_column_id in ['buyer_national_id', 'buyer_address', 'buyer_name']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        field_mapping = {
                            'buyer_national_id': 'purchase__buyer_national_id',
                            'buyer_address': 'purchase__address',
                            'buyer_name': 'purchase__buyer_name'
                        }
                        field_name = field_mapping.get(filter_column_id)
                        if field_name:
                            if filter_type == 'include':
                                filter_conditions &= Q(**{f'{field_name}__in': values})
                            else:
                                filter_conditions &= ~Q(**{f'{field_name}__in': values})
                
                elif filter_column_id == 'importer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__cargo__vared_konandeh__name__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__cargo__vared_konandeh__name__in=values)
                
                elif filter_column_id == 'product_type':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # تبدیل نمایش فارسی به کد محصول
                        from core.CargoProductModel import CargoProduct
                        product_choices = dict(CargoProduct.PRODUCT_TYPES)
                        reverse_product_map = {v: k for k, v in product_choices.items()}
                        product_codes = []
                        for v in values:
                            if v in reverse_product_map:
                                product_codes.append(reverse_product_map[v])
                            else:
                                product_codes.append(v)
                        
                        if product_codes:
                            if filter_type == 'include':
                                filter_conditions &= Q(purchase__cargo__product_type__in=product_codes)
                            else:
                                filter_conditions &= ~Q(purchase__cargo__product_type__in=product_codes)
                
                elif filter_column_id == 'product_country':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # تبدیل نمایش فارسی به کد کشور
                        from core.CargoProductModel import CargoProduct
                        country_choices = dict(CargoProduct.COUNTRIES)
                        reverse_country_map = {v: k for k, v in country_choices.items()}
                        country_codes = []
                        for v in values:
                            if v in reverse_country_map:
                                country_codes.append(reverse_country_map[v])
                            else:
                                country_codes.append(v)
                        
                        if country_codes:
                            if filter_type == 'include':
                                filter_conditions &= Q(purchase__cargo__country__in=country_codes)
                            else:
                                filter_conditions &= ~Q(purchase__cargo__country__in=country_codes)
                
                elif filter_column_id == 'successful_send_date':
                    # فیلتر تاریخی شمسی
                    date_conditions = Q()
                    for date_str in values:
                        try:
                            if date_str and date_str.strip() and '/' in date_str:
                                # استفاده از تابع parse_jalali_date برای تبدیل صحیح تاریخ شمسی
                                date_obj = parse_jalali_date(date_str)
                                if date_obj:
                                    date_conditions |= Q(purchase__successful_send_date=date_obj)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"خطا در پارس تاریخ {date_str}: {str(e)}")
                            continue
                    
                    if date_conditions:
                        if filter_type == 'include':
                            filter_conditions &= date_conditions
                        else:
                            filter_conditions &= ~date_conditions
                
                elif filter_column_id in ['factor_sodoor_season', 'buyer_postal_code']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{filter_column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{filter_column_id}__in': values})
                
                elif filter_column_id == 'factor_date':
                    # فیلتر تاریخی شمسی برای تاریخ ثبت فاکتور
                    date_conditions = Q()
                    for date_str in values:
                        try:
                            if date_str and date_str.strip() and '/' in date_str:
                                # استفاده از تابع parse_jalali_date برای تبدیل صحیح تاریخ شمسی
                                date_obj = parse_jalali_date(date_str)
                                if date_obj:
                                    date_conditions |= Q(factor_date=date_obj)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"خطا در پارس تاریخ {date_str}: {str(e)}")
                            continue
                    
                    if date_conditions:
                        if filter_type == 'include':
                            filter_conditions &= date_conditions
                        else:
                            filter_conditions &= ~date_conditions
                
            
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
                'NOT_SENT_TO_BKI': 'ارسال نشده به بازارگاه',
                'SENT_TO_BKI': 'ارسال شده به بازارگاه'
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
        
        # ستون‌های مربوط به purchase
        elif column_id == 'cargo':
            values_queryset = base_queryset.exclude(purchase__cargo__isnull=True)\
                .values_list('purchase__cargo__cottage', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'company_price':
            values_queryset = base_queryset.exclude(purchase__company_price__isnull=True)\
                .exclude(purchase__company_price=0)\
                .values_list('purchase__company_price', flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'customer_price':
            values_queryset = base_queryset.exclude(purchase__customer_price__isnull=True)\
                .exclude(purchase__customer_price=0)\
                .values_list('purchase__customer_price', flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'total_sales_amount':
            values_queryset = base_queryset.exclude(total_sales_amount__isnull=True)\
                .exclude(total_sales_amount=0)\
                .values_list('total_sales_amount', flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'total_purchase_amount':
            values_queryset = base_queryset.exclude(total_purchase_amount__isnull=True)\
                .exclude(total_purchase_amount=0)\
                .values_list('total_purchase_amount', flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'buyer_national_id':
            values_queryset = base_queryset.exclude(purchase__buyer_national_id__isnull=True)\
                .exclude(purchase__buyer_national_id='')\
                .values_list('purchase__buyer_national_id', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'buyer_address':
            values_queryset = base_queryset.exclude(purchase__address__isnull=True)\
                .exclude(purchase__address='')\
                .values_list('purchase__address', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'buyer_name':
            values_queryset = base_queryset.exclude(purchase__buyer_name__isnull=True)\
                .exclude(purchase__buyer_name='')\
                .values_list('purchase__buyer_name', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'demand_amount':
            values_queryset = base_queryset.exclude(purchase__total_weight__isnull=True)\
                .exclude(purchase__total_weight=0)\
                .values_list('purchase__total_weight', flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'importer':
            values_queryset = base_queryset.exclude(purchase__cargo__vared_konandeh__isnull=True)\
                .values_list('purchase__cargo__vared_konandeh__name', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'product_type':
            values_queryset = base_queryset.exclude(purchase__cargo__product_type__isnull=True)\
                .exclude(purchase__cargo__product_type='')\
                .values_list('purchase__cargo__product_type', flat=True).distinct()
            # تبدیل کدهای محصول به نمایش فارسی
            from core.CargoProductModel import CargoProduct
            product_choices = dict(CargoProduct.PRODUCT_TYPES)
            values = set([product_choices.get(product_type, product_type) for product_type in values_queryset if product_type])
            
        elif column_id == 'successful_send_date':
            values_queryset = base_queryset.exclude(purchase__successful_send_date__isnull=True)\
                .values_list('purchase__successful_send_date', flat=True).distinct()
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])
            
        elif column_id == 'factor_sodoor_season':
            values_queryset = base_queryset.exclude(factor_sodoor_season__isnull=True)\
                .exclude(factor_sodoor_season='')\
                .values_list('factor_sodoor_season', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'buyer_postal_code':
            values_queryset = base_queryset.exclude(buyer_postal_code__isnull=True)\
                .exclude(buyer_postal_code='')\
                .values_list('buyer_postal_code', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'factor_date':
            values_queryset = base_queryset.exclude(factor_date__isnull=True)\
                .values_list('factor_date', flat=True).distinct()
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])

        elif column_id == 'product_country':
            values_queryset = base_queryset.exclude(purchase__cargo__country__isnull=True)\
                .exclude(purchase__cargo__country='')\
                .values_list('purchase__cargo__country', flat=True).distinct()
            # تبدیل کدهای کشور به نمایش فارسی
            from core.CargoProductModel import CargoProduct
            country_choices = dict(CargoProduct.COUNTRIES)
            values = set([country_choices.get(country, country) for country in values_queryset if country])
        
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
                if isinstance(data['barnameh_date'], str) and data['barnameh_date'].strip():
                    barnameh.barnameh_date = parse_jalali_date(data['barnameh_date'])
                elif data['barnameh_date'] is None:
                    barnameh.barnameh_date = None
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
        
        if 'factor_date' in data:
            try:
                if isinstance(data['factor_date'], str) and data['factor_date'].strip():
                    barnameh.factor_date = parse_jalali_date(data['factor_date'])
                elif data['factor_date'] is None:
                    barnameh.factor_date = None
                else:
                    barnameh.factor_date = data['factor_date']
            except Exception as e:
                logger.error(f"خطا در تبدیل تاریخ ثبت فاکتور: {str(e)}")
                return {
                    'success': False,
                    'message': f'خطا در تبدیل تاریخ ثبت فاکتور: {str(e)}'
                }
        
        # Check if barnameh is complete
        if all([barnameh.number, barnameh.serial, barnameh.tonnage]):
            barnameh.status = 'SENT_TO_BKI'
        else:
            barnameh.status = 'NOT_SENT_TO_BKI'
        
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
    per_page_param = request.GET.get('per_page', 100)
    
    # بررسی گزینه "نمایش همه"
    if per_page_param == 'all':
        per_page = 10000  # عدد بزرگ برای نمایش همه
    else:
        try:
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            per_page = 100
    
    # بررسی اینکه آیا درخواست AJAX است
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # فیلدهای ضروری برای QuerySet
    selected_fields = [
        'id', 'number', 'serial', 'tonnage', 'status', 'driver_name', 
        'driver_phone', 'vehicle_plate', 'receiver_name', 'destination', 
        'barnameh_date', 'purchase_number', 'shenase_takhsis_code',
        'is_sent_to_bki', 'barnameh_created_at', 'factor_sodoor_season', 
        'is_factored', 'is_created_by_excel', 'factor_date', 'buyer_postal_code',
        'is_sent_to_bki_at', 'is_created_by_excel_at', 'barnameh_updated_at',
        'product_country',
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
    ).filter(type='Bazargah').order_by('-barnameh_created_at')
    
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
        
        # پردازش تاریخ بارنامه
        barnameh_date = None
        if data['barnameh_date']:
            try:
                barnameh_date = parse_jalali_date(data['barnameh_date'])
            except Exception as e:
                logger.error(f"خطا در تبدیل تاریخ بارنامه: {str(e)}")
                messages.error(request, f'خطا در تبدیل تاریخ: {str(e)}')
                return render(request, 'bki_barnameh/barnameh_create.html')
        
        barnameh = Barnameh.objects.create(
            number=data['number'],
            serial=data['serial'],
            tonnage=data['tonnage'] if data['tonnage'] else None,
            driver_phone=data['driver_phone'],
            driver_name=data['driver_name'],
            vehicle_plate=data['vehicle_plate'],
            receiver_name=data['receiver_name'],
            destination=data['destination'],
            barnameh_date=barnameh_date,
            purchase_number=data['purchase_number'],
            shenase_takhsis_code=data['shenase_takhsis_code'],
            status='NOT_SENT_TO_BKI'
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
                    status='SENT_TO_BKI' if all([data.get('number'), data.get('serial'), data.get('tonnage')]) else 'NOT_SENT_TO_BKI'
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
                           'receiver_name', 'destination', 'barnameh_date', 'factor_date']
            
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
                        
                        elif field_to_update == 'factor_date':
                            try:
                                # تبدیل تاریخ شمسی به فرمت مناسب برای factor_date
                                parts = new_value.split('/')
                                if len(parts) == 3:
                                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                                    processed_value = jdatetime.date(year, month, day)
                                else:
                                    error_count += 1
                                    error_message = f'فرمت تاریخ ثبت فاکتور معتبر نیست: {new_value}. از فرمت 1404/02/04 استفاده کنید.'
                                    error_messages.append(error_message)
                                    error_details.append({
                                        'id': barnameh.id,
                                        'number': barnameh.number,
                                        'serial': barnameh.serial,
                                        'error': error_message
                                    })
                                    logger.error(f"فرمت تاریخ ثبت فاکتور معتبر نیست: {new_value}. از فرمت 1404/02/04 استفاده کنید.")
                                    continue
                            except Exception as e:
                                error_count += 1
                                error_message = f'خطا در تبدیل تاریخ ثبت فاکتور: {str(e)}'
                                error_messages.append(error_message)
                                error_details.append({
                                    'id': barnameh.id,
                                    'number': barnameh.number,
                                    'serial': barnameh.serial,
                                    'error': error_message
                                })
                                logger.error(f"خطا در تبدیل تاریخ ثبت فاکتور: {str(e)}")
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
        # دریافت ستون‌های انتخاب شده از کوکی یا پیش‌فرض
        from .views import get_barnameh_columns_from_cookie
        selected_columns = get_barnameh_columns_from_cookie(request)
        if not selected_columns:
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
    # بهینه‌سازی کوئری با select_related برای جلوگیری از N+1 queries
    barnamehs = Barnameh.objects.select_related(
        'purchase', 
        'purchase__cargo'
    ).filter(id__in=barnameh_ids).order_by('-barnameh_created_at')
    
    logger.warning(f"Found {barnamehs.count()} barnamehs")
    
    # لاگ کردن اطلاعات اضافی برای دیباگ
    for barnameh in barnamehs[:5]:  # فقط 5 مورد اول
        logger.warning(f"Barnameh {barnameh.id}: purchase={barnameh.purchase}, cargo={barnameh.purchase.cargo if barnameh.purchase else None}")
    
    if barnamehs.count() == 0:
        logger.warning("ERROR: No barnamehs found!")
        return JsonResponse({'status': 'error', 'message': 'هیچ بارنامه‌ای با شناسه‌های داده شده یافت نشد'}, status=400)
    
    wb = Workbook()
    ws = wb.active
    ws.title = "لیست بارنامه‌ها"
    
    # تنظیم گردش متن از راست به چپ برای کل صفحه
    ws.sheet_view.rightToLeft = True
    
    # استایل‌های ساده برای scalability
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')  # خاکستری ساده
    alignment = Alignment(horizontal='right', vertical='center')
    
    # مپینگ کامل ستون‌ها به فیلدهای مدل بارنامه - ترتیب اولویت
    column_mapping = {
        'number': ('شماره بارنامه', lambda b: b.number or "تعیین نشده"),
        'serial': ('سریال', lambda b: b.serial or "تعیین نشده"),
        'barnameh_date': ('تاریخ بارنامه', lambda b: b.barnameh_date.strftime("%Y/%m/%d") if b.barnameh_date else "-"),
        'driver_name': ('نام راننده', lambda b: b.driver_name or "-"),
        'driver_phone': ('تلفن راننده', lambda b: b.driver_phone or "-"),
        'vehicle_plate': ('پلاک', lambda b: b.vehicle_plate or "-"),
        'tonnage': ('وزن', lambda b: f"{int(b.tonnage)}" if b.tonnage else "0"),
        'shenase_takhsis_code': ('شناسه تخصیص', lambda b: b.shenase_takhsis_code or "-"),
        'status': ('وضعیت', lambda b: b.get_status_display() if b.status else "-"),
        'receiver_name': ('نام تحویل گیرنده', lambda b: b.get_delivery_receiver_name() or "-"),
        'destination': ('آدرس تحویل', lambda b: b.get_delivery_address() or "-"),
        'purchase_number': ('شماره خرید', lambda b: b.purchase_number or "-"),
        'cargo': ('کوتاژ', lambda b: str(b.get_cargo()) if b.get_cargo() else "-"),
        'company_price': ('فی خرید', lambda b: f"{b.get_company_price():,}" if b.get_company_price() and b.get_company_price() > 0 else "0"),
        'customer_price': ('فی فروش', lambda b: f"{b.get_customer_price():,}" if b.get_customer_price() and b.get_customer_price() > 0 else "0"),
        'total_sales_amount': ('مبلغ کل فروش', lambda b: f"{b.get_total_sales_amount():,.0f}" if b.get_total_sales_amount() else "-"),
        'total_purchase_amount': ('مبلغ کل خرید', lambda b: f"{b.get_total_purchase_amount():,.0f}" if b.get_total_purchase_amount() and b.get_total_purchase_amount() > 0 else "0"),
        'buyer_name': ('نام خریدار', lambda b: b.get_buyer_name() or "-"),
        'buyer_national_id': ('شماره ملی خریدار', lambda b: b.get_buyer_national_code() or "-"),
        'buyer_postal_code': ('کدپستی خریدار', lambda b: b.get_buyer_postal_code() or "-"),
        'buyer_address': ('آدرس خریدار', lambda b: b.get_buyer_address() or "-"),
        'demand_amount': ('میزان تقاضا', lambda b: f"{b.get_demand_amount()}" if b.get_demand_amount() else "-"),
        'importer': ('واردکننده', lambda b: str(b.get_importer()) if b.get_importer() else "-"),
        'product_type': ('محصول', lambda b: b.get_product_type() or "-"),
        'product_country': ('کشور محصول', lambda b: b.get_product_country() or "-"),
        'successful_send_date': ('تاریخ ارسال موفق به بازارگاه', lambda b: b.get_successful_send_date().strftime("%Y/%m/%d") if b.get_successful_send_date() else "-"),
        'is_sent_to_bki': ('ارسال به بازارگاه', lambda b: "بله" if b.is_sent_to_bki else "خیر"),
        'created_at': ('تاریخ ایجاد', lambda b: b.barnameh_created_at.strftime("%Y/%m/%d") if b.barnameh_created_at else "-"),
        'factor_sodoor_season': ('زمان صدور فاکتور فصل', lambda b: b.factor_sodoor_season or "-"),
        'factor_date': ('تاریخ ثبت فاکتور در سامانه مؤدیان', lambda b: b.factor_date.strftime("%Y/%m/%d") if b.factor_date else "-"),
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
                    # برای فیلدهای عددی، مقدار پیش‌فرض 0 قرار می‌دهیم
                    if col in ['company_price', 'customer_price', 'total_sales_amount', 'total_purchase_amount', 'tonnage']:
                        row.append("0")
                    else:
                        row.append("-")
        
        ws.append(row)
        
        # تنظیم استایل برای سطرهای داده
        for j, cell in enumerate(ws[row_idx], 1):
            cell.alignment = alignment
        
        row_idx += 1
    
    # تنظیم عرض ستون‌ها - ساده
    for i in range(1, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 12
    
    # اضافه کردن فریز به سطر هدر
    ws.freeze_panes = "A2"
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"barnameh_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    logger.warning(f"Excel file created: {filename}")
    return response


@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["GET"])
def get_barnameh_logs(request, barnameh_id):
    """API برای دریافت لاگ‌های بارنامه"""
    try:
        # دریافت بارنامه
        barnameh = get_object_or_404(Barnameh, id=barnameh_id)
        
        # دریافت لاگ‌های بارنامه
        logs = BarnamehLog.objects.filter(barnameh=barnameh).order_by('-log_date')
        
        # تبدیل لاگ‌ها به فرمت JSON
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'message': log.log_message,
                'date': log.log_date.strftime('%Y/%m/%d %H:%M:%S'),
                'timestamp': log.log_date.isoformat()
            })
        
        return JsonResponse({
            'status': 'success',
            'barnameh_id': barnameh_id,
            'barnameh_number': barnameh.number,
            'barnameh_serial': barnameh.serial,
            'logs': logs_data,
            'total_logs': len(logs_data)
        })
        
    except Barnameh.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'بارنامه یافت نشد'
        }, status=404)
    except Exception as e:
        logger.error(f"خطا در دریافت لاگ‌های بارنامه {barnameh_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت لاگ‌ها: {str(e)}'
        }, status=500)


@role_required('logistics_manager', 'admin', 'financial_manager')
@require_http_methods(["GET"])
def fast_barnameh_report_pdf(request):
    """
    گزارش PDF از خریدهای 4 روز اخیر که بارنامه سریع (کمتر از 3 روز) دارند
    به تفکیک کارشناس فروش - با پشتیبانی کامل از فارسی
    """
    try:
        from core.PurchaseModel import Purchase
        from core.SalesAgentModel import SalesAgent
        from django.db.models import Prefetch
        
        # تابع کمکی برای پردازش متن فارسی
        def process_persian_text(text):
            """تبدیل متن فارسی به حالت صحیح برای نمایش در PDF"""
            if text is None:
                return "-"
            
            text = str(text).strip()
            if not text:
                return "-"
            
            try:
                # بازسازی متن فارسی - فقط اگر حروف فارسی/عربی داشت
                if any(ord(char) > 127 for char in text):  # اگر کاراکتر غیر ASCII داشت
                    reshaped_text = arabic_reshaper.reshape(text)
                    # تبدیل به BIDI
                    bidi_text = get_display(reshaped_text)
                    return bidi_text
                else:
                    # اگر فقط کاراکترهای انگلیسی/عددی بود، بدون تغییر برگردان
                    return text
            except Exception as e:
                logger.warning(f"خطا در پردازش متن فارسی '{text}': {str(e)}")
                return text
        
        # تابع کمکی برای تبدیل مقادیر به متن امن
        def safe_text(value, default='-'):
            """تبدیل مقادیر به متن امن"""
            if value is None:
                return default
            return process_persian_text(str(value))
        
        # تابع کمکی برای فرمت کردن اعداد
        def format_number(value, default='0'):
            """تبدیل اعداد به متن فارسی با کاما"""
            if value is None or value == 0:
                return default
            try:
                return process_persian_text(f"{int(value):,}")
            except (ValueError, TypeError):
                return default
        
        # ثبت فونت فارسی
        BIDI_ENABLED = True
        try:
            font_path = os.path.join(settings.BASE_DIR, 'ERP', 'static', 'fonts', 'Vazir.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Vazir', font_path))
            else:
                # اگر فونت وزیر موجود نبود، از فونت پیش‌فرض استفاده کن
                BIDI_ENABLED = False
                logger.warning("فونت وزیر یافت نشد، از فونت پیش‌فرض استفاده می‌شود")
        except Exception as e:
            BIDI_ENABLED = False
            logger.warning(f"خطا در بارگذاری فونت فارسی: {str(e)}")
        
        # محاسبه تاریخ‌های مورد نیاز
        now = timezone.now()
        four_days_ago = now - timedelta(days=7)
        
        logger.info(f"گزارش بارنامه‌های سریع از {four_days_ago} تا {now}")
        
        # یافتن خریدهای 4 روز اخیر که دارای بارنامه هستند
        purchases_with_barnamehs = Purchase.objects.filter(
            created_at__gte=four_days_ago
        ).prefetch_related(
            'barnamehs',
            'unique_sales_agent',
            'customer',
            'cargo'
        ).filter(
            barnamehs__isnull=False
        ).distinct()
        
        # فیلتر کردن همه بارنامه‌هایی که زودتر از 3 روز آمده‌اند
        fast_purchases = []
        for purchase in purchases_with_barnamehs:
            for barnameh in purchase.barnamehs.all():
                if barnameh.barnameh_created_at:
                    # محاسبه تفاوت زمان بین ثبت خرید و صدور بارنامه
                    time_diff = barnameh.barnameh_created_at - purchase.created_at
                    if time_diff.days <= 3:  # کمتر از 3 روز
                        # محاسبه دقیق تفاوت روز
                        purchase_date = purchase.created_at.date()
                        barnameh_date = barnameh.barnameh_created_at.date()
                        actual_days_diff = (barnameh_date - purchase_date).days
                        
                        fast_purchases.append({
                            'purchase': purchase,
                            'barnameh': barnameh,
                            'days_diff': actual_days_diff,
                            'hours_diff': time_diff.total_seconds() / 3600
                        })
                        # حذف break تا همه بارنامه‌های سریع آن خرید اضافه شوند
        
        # گروه‌بندی بر اساس کارشناس فروش
        sales_agent_groups = {}
        for item in fast_purchases:
            purchase = item['purchase']
            sales_agent = purchase.unique_sales_agent
            
            # اگر کارشناس فروش مشخص نباشد، در گروه "نامشخص" قرار بده
            if not sales_agent:
                agent_key = "نامشخص"
                agent_name = "کارشناس فروش نامشخص"
                agent_type = "نامشخص"
            else:
                agent_key = str(sales_agent.id)
                agent_name = sales_agent.name or sales_agent.user.get_full_name() or sales_agent.user.username
                
                # تشخیص نوع کارشناس (سوپریوزر یا عادی)
                if sales_agent.user and sales_agent.user.is_superuser:
                    agent_type = "سوپریوزر"
                    agent_name = f"{agent_name} (سوپریوزر)"
                else:
                    agent_type = "کارشناس فروش"
            
            if agent_key not in sales_agent_groups:
                sales_agent_groups[agent_key] = {
                    'name': agent_name,
                    'type': agent_type,
                    'purchases': []
                }
            
            sales_agent_groups[agent_key]['purchases'].append(item)
        
        # ایجاد PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f"fast_barnameh_report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        story = []
        
        # تعریف استایل‌های فارسی
        styles = getSampleStyleSheet()
        
        # استایل عنوان اصلی
        title_style = ParagraphStyle(
            'FarsiTitle',
            fontName='Vazir' if BIDI_ENABLED else 'Helvetica-Bold',
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
            leading=22
        )
        
        # استایل عنوان کارشناس فروش
        agent_title_style = ParagraphStyle(
            'FarsiAgentTitle',
            fontName='Vazir' if BIDI_ENABLED else 'Helvetica-Bold',
            fontSize=16,
            spaceAfter=15,
            alignment=TA_CENTER,
            leading=20
        )
        
        # استایل متن عادی
        normal_style = ParagraphStyle(
            'FarsiNormal',
            fontName='Vazir' if BIDI_ENABLED else 'Helvetica',
            fontSize=11,
            spaceAfter=8,
            alignment=TA_RIGHT,
            leading=16
        )
        
        # استایل زیرعنوان
        subtitle_style = ParagraphStyle(
            'FarsiSubtitle',
            fontName='Vazir' if BIDI_ENABLED else 'Helvetica-Bold',
            fontSize=13,
            spaceAfter=10,
            alignment=TA_RIGHT,
            leading=18
        )
        
        # اگر هیچ خریدی پیدا نشد
        if not fast_purchases:
            story.append(Paragraph(process_persian_text("گزارش بارنامه‌های سریع"), title_style))
            story.append(Spacer(1, 20))
            story.append(Paragraph(process_persian_text("هیچ خرید با بارنامه سریع در 4 روز اخیر یافت نشد."), normal_style))
            
            doc.build(story)
            pdf = buffer.getvalue()
            buffer.close()
            response.write(pdf)
            return response
        
        # تاریخ‌های شمسی
        import jdatetime
        jalali_start = jdatetime.datetime.fromgregorian(datetime=four_days_ago).strftime('%Y/%m/%d')
        jalali_end = jdatetime.datetime.fromgregorian(datetime=now).strftime('%Y/%m/%d')
        
        # برای هر کارشناس فروش صفحه کاملاً جداگانه
        first_page = True
        for agent_key, agent_data in sales_agent_groups.items():
            if not first_page:  # اگر اولین صفحه نیست، صفحه جدید بساز
                story.append(PageBreak())
            first_page = False
            
            # عنوان اصلی گزارش برای هر کارشناس
            story.append(Paragraph(process_persian_text("گزارش خریدهای دارای بارنامه سریع"), title_style))
            story.append(Spacer(1, 15))
            
            # اطلاعات کلی گزارش
            summary_info = [
                f"از تاریخ: {jalali_start} تا {jalali_end}",
                f"{agent_data['type']}: {agent_data['name']}",
                f"تعداد خریدهای سریع: {len(agent_data['purchases'])}"
            ]
            
            for info in summary_info:
                story.append(Paragraph(process_persian_text(info), normal_style))
            
            story.append(Spacer(1, 20))
            
            # گروه‌بندی بارنامه‌ها بر اساس خرید
            purchases_with_barnamehs = {}
            for item in agent_data['purchases']:
                purchase = item['purchase']
                if purchase.id not in purchases_with_barnamehs:
                    purchases_with_barnamehs[purchase.id] = {
                        'purchase': purchase,
                        'barnamehs': []
                    }
                purchases_with_barnamehs[purchase.id]['barnamehs'].append(item)
            
            # نمایش هر خرید با بارنامه‌هایش
            for purchase_id, purchase_data in purchases_with_barnamehs.items():
                purchase = purchase_data['purchase']
                barnamehs = purchase_data['barnamehs']
                
                # عنوان خرید
                purchase_title = f"خرید شماره: {purchase.purchase_number or 'نامشخص'}"
                story.append(Paragraph(process_persian_text(purchase_title), subtitle_style))
                story.append(Spacer(1, 8))
                
                # اطلاعات کلی خرید
                purchase_info_data = [
                    [
                        process_persian_text('وزن خرید (کیلوگرم)'),
                        process_persian_text('نام مشتری'),
                        process_persian_text('محصول'),
                        process_persian_text('تعداد بارنامه‌های سریع')
                    ],
                    [
                        format_number(purchase.order_weight) if purchase.order_weight else "-",
                        process_persian_text(purchase.customer.name) if purchase.customer and purchase.customer.name else "-",
                        process_persian_text(str(purchase.cargo)) if purchase.cargo else "-",
                        process_persian_text(str(len(barnamehs)))
                    ]
                ]
                
                purchase_info_table = Table(purchase_info_data, colWidths=[40*mm, 50*mm, 50*mm, 35*mm])
                purchase_info_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('FONTNAME', (0, 0), (-1, -1), 'Vazir' if BIDI_ENABLED else 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                
                story.append(purchase_info_table)
                story.append(Spacer(1, 12))
                
                # جدول بارنامه‌های این خرید
                barnameh_table_data = [
                    [
                        process_persian_text('ردیف'),
                        process_persian_text('شناسه تخصیص'),
                        process_persian_text('شماره بارنامه'),
                        process_persian_text('سریال'),
                        process_persian_text('وزن (کیلوگرم)'),
                        process_persian_text('نام راننده'),
                        process_persian_text('شماره راننده'),
                        process_persian_text('پلاک'),
                        process_persian_text('تفاوت (روز)')
                    ]
                ]
                
                for idx, item in enumerate(barnamehs, 1):
                    barnameh = item['barnameh']
                    
                    # بررسی شناسه تخصیص از چندین منبع
                    shenase_takhsis_value = None
                    if purchase.shenase_takhsis:
                        shenase_takhsis_value = purchase.shenase_takhsis
                    elif hasattr(purchase, 'shenase_takhsis_set') and purchase.shenase_takhsis_set.exists():
                        shenase_takhsis_value = purchase.shenase_takhsis_set.first().code
                    elif barnameh.shenase_takhsis_code:
                        shenase_takhsis_value = barnameh.shenase_takhsis_code
                    
                    shenase_takhsis = safe_text(shenase_takhsis_value)
                    barnameh_number = safe_text(barnameh.number)
                    serial_text = safe_text(barnameh.serial)
                    tonnage_text = format_number(barnameh.tonnage) if barnameh.tonnage else "-"
                    driver_name = process_persian_text(barnameh.driver_name) if barnameh.driver_name else "-"
                    driver_phone = safe_text(barnameh.driver_phone) if barnameh.driver_phone else "-"
                    plate_text = safe_text(barnameh.vehicle_plate) if barnameh.vehicle_plate else "-"
                    days_diff = f"{item['days_diff']}"
                    
                    barnameh_table_data.append([
                        process_persian_text(str(idx)),
                        shenase_takhsis,
                        barnameh_number,
                        serial_text,
                        tonnage_text,
                        driver_name,
                        driver_phone,
                        plate_text,
                        days_diff
                    ])
                
                barnameh_table = Table(barnameh_table_data, colWidths=[15*mm, 25*mm, 25*mm, 20*mm, 20*mm, 25*mm, 25*mm, 20*mm, 15*mm])
                barnameh_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('FONTNAME', (0, 0), (-1, -1), 'Vazir' if BIDI_ENABLED else 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                
                story.append(barnameh_table)
                story.append(Spacer(1, 15))
        
        # ایجاد PDF
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        
        logger.info(f"گزارش PDF با پشتیبانی فارسی ایجاد شد: {filename}")
        return response
        
    except Exception as e:
        logger.error(f"خطا در ایجاد گزارش PDF: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در ایجاد گزارش: {str(e)}'
        }, status=500)

@csrf_exempt
@role_required('logistics_manager', 'admin', 'financial_manager')
def export_full_barnameh_excel(request):
    """
    خروجی اکسل کامل از همه بارنامه‌ها با تمام ستون‌ها و امکان انتخاب بازه تاریخ
    """
    logger.warning(f"خروجی اکسل کامل توسط {request.user.username} با آی‌پی {get_client_ip(request)} آغاز شد")
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'فقط درخواست POST پذیرفته می‌شود'}, status=405)
    
    try:
        # دریافت پارامترهای تاریخ
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        
        logger.warning(f"بازه تاریخی درخواستی: از {from_date} تا {to_date}")
        
        # تست تبدیل تاریخ برای دیباگ
        if from_date:
            try:
                test_from = jalali_to_gregorian_date(from_date)
                logger.warning(f"تست تبدیل از تاریخ: {from_date} -> {test_from}")
            except Exception as e:
                logger.error(f"خطا در تست تبدیل از تاریخ: {e}")
        
        if to_date:
            try:
                test_to = jalali_to_gregorian_date(to_date)
                logger.warning(f"تست تبدیل تا تاریخ: {to_date} -> {test_to}")
            except Exception as e:
                logger.error(f"خطا در تست تبدیل تا تاریخ: {e}")
        
        # ایجاد QuerySet پایه با select_related برای بهینه‌سازی
        base_queryset = Barnameh.objects.select_related(
            'purchase', 
            'shenase_takhsis',
            'purchase__cargo',
            'purchase__cargo__vared_konandeh'
        ).filter(type='Bazargah').order_by('-barnameh_created_at')
        
        # اعمال فیلتر تاریخ اگر مشخص شده باشد
        if from_date or to_date:
            
            if from_date:
                try:
                    # تبدیل تاریخ شمسی به میلادی
                    from_date_obj = jalali_to_gregorian_date(from_date)
                    if from_date_obj:
                        # فیلتر روی barnameh_date (تاریخ بارنامه) نه barnameh_created_at
                        base_queryset = base_queryset.filter(barnameh_date__gte=from_date_obj)
                        logger.info(f"فیلتر از تاریخ شمسی {from_date} (میلادی: {from_date_obj}) اعمال شد")
                except ValueError as e:
                    logger.error(f"فرمت تاریخ شروع نامعتبر: {from_date} - {str(e)}")
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'فرمت تاریخ شروع نامعتبر: {from_date}'
                    }, status=400)
            
            if to_date:
                try:
                    # تبدیل تاریخ شمسی به میلادی
                    to_date_obj = jalali_to_gregorian_date(to_date)
                    if to_date_obj:
                        # فیلتر روی barnameh_date (تاریخ بارنامه) نه barnameh_created_at
                        base_queryset = base_queryset.filter(barnameh_date__lte=to_date_obj)
                        logger.info(f"فیلتر تا تاریخ شمسی {to_date} (میلادی: {to_date_obj}) اعمال شد")
                except ValueError as e:
                    logger.error(f"فرمت تاریخ پایان نامعتبر: {to_date} - {str(e)}")
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'فرمت تاریخ پایان نامعتبر: {to_date}'
                    }, status=400)
        
        # شمارش کل بارنامه‌ها
        total_count = base_queryset.count()
        logger.warning(f"تعداد کل بارنامه‌های قابل خروجی: {total_count}")
        
        if total_count == 0:
            return JsonResponse({
                'status': 'error', 
                'message': 'هیچ بارنامه‌ای در بازه تاریخی انتخاب شده یافت نشد'
            }, status=400)
        
        # محدودیت تعداد برای جلوگیری از مشکلات عملکردی
        max_export_limit = 50000  # حداکثر 50,000 بارنامه
        if total_count > max_export_limit:
            return JsonResponse({
                'status': 'error',
                'message': f'تعداد بارنامه‌ها ({total_count:,}) بیش از حد مجاز ({max_export_limit:,}) است. لطفاً بازه تاریخی کوچک‌تری انتخاب کنید.'
            }, status=400)
        
        # دریافت تمام ستون‌های موجود (بجز actions)
        all_columns_data = get_all_barnameh_columns()
        all_column_ids = [col['id'] for col in all_columns_data if col['id'] != 'actions']
        
        logger.warning(f"تمام ستون‌های قابل خروجی: {len(all_column_ids)} ستون")
        
        # تولید فایل اکسل
        return _export_barnameh_excel_full(base_queryset, all_column_ids, from_date, to_date)
        
    except Exception as e:
        import traceback
        logger.error(f"خطا در خروجی اکسل کامل: {str(e)}, {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error', 
            'message': f'خطا در تولید فایل اکسل: {str(e)}'
        }, status=500)

def _export_barnameh_excel_full(queryset, selected_columns, from_date=None, to_date=None):
    """پردازش و ایجاد فایل اکسل کامل برای همه بارنامه‌ها"""
    
    logger.warning(f"شروع تولید فایل اکسل کامل برای {queryset.count()} بارنامه با {len(selected_columns)} ستون")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "لیست کامل بارنامه‌ها"
    
    # تنظیم گردش متن از راست به چپ
    ws.sheet_view.rightToLeft = True
    
    # استایل‌های ساده برای scalability
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')  # خاکستری ساده
    alignment = Alignment(horizontal='right', vertical='center')
    
    # مپینگ کامل ستون‌ها - ترتیب اولویت
    column_mapping = {
        'number': ('شماره بارنامه', lambda b: b.number or "تعیین نشده"),
        'serial': ('سریال', lambda b: b.serial or "تعیین نشده"),
        'barnameh_date': ('تاریخ بارنامه', lambda b: b.barnameh_date.strftime("%Y/%m/%d") if b.barnameh_date else "-"),
        'driver_name': ('نام راننده', lambda b: b.driver_name or "-"),
        'driver_phone': ('تلفن راننده', lambda b: b.driver_phone or "-"),
        'vehicle_plate': ('پلاک', lambda b: b.vehicle_plate or "-"),
        'tonnage': ('وزن', lambda b: f"{int(b.tonnage)}" if b.tonnage else "0"),
        'shenase_takhsis_code': ('شناسه تخصیص', lambda b: b.shenase_takhsis_code or "-"),
        'status': ('وضعیت', lambda b: b.get_status_display() if b.status else "-"),
        'receiver_name': ('نام تحویل گیرنده', lambda b: b.get_delivery_receiver_name() or "-"),
        'destination': ('آدرس تحویل', lambda b: b.get_delivery_address() or "-"),
        'purchase_number': ('شماره خرید', lambda b: b.purchase_number or "-"),
        'cargo': ('کوتاژ', lambda b: str(b.get_cargo()) if b.get_cargo() else "-"),
        'company_price': ('فی خرید', lambda b: f"{b.get_company_price():,}" if b.get_company_price() and b.get_company_price() > 0 else "0"),
        'customer_price': ('فی فروش', lambda b: f"{b.get_customer_price():,}" if b.get_customer_price() and b.get_customer_price() > 0 else "0"),
        'total_sales_amount': ('مبلغ کل فروش', lambda b: f"{b.get_total_sales_amount():,.0f}" if b.get_total_sales_amount() else "-"),
        'total_purchase_amount': ('مبلغ کل خرید', lambda b: f"{b.get_total_purchase_amount():,.0f}" if b.get_total_purchase_amount() and b.get_total_purchase_amount() > 0 else "0"),
        'buyer_name': ('نام خریدار', lambda b: b.get_buyer_name() or "-"),
        'buyer_national_id': ('شماره ملی خریدار', lambda b: b.get_buyer_national_code() or "-"),
        'buyer_postal_code': ('کدپستی خریدار', lambda b: b.get_buyer_postal_code() or "-"),
        'buyer_address': ('آدرس خریدار', lambda b: b.get_buyer_address() or "-"),
        'demand_amount': ('میزان تقاضا', lambda b: f"{b.get_demand_amount()}" if b.get_demand_amount() else "-"),
        'importer': ('واردکننده', lambda b: str(b.get_importer()) if b.get_importer() else "-"),
        'product_type': ('محصول', lambda b: b.get_product_type() or "-"),
        'product_country': ('کشور محصول', lambda b: b.get_product_country() or "-"),
        'successful_send_date': ('تاریخ ارسال موفق به بازارگاه', lambda b: b.get_successful_send_date().strftime("%Y/%m/%d") if b.get_successful_send_date() else "-"),
        'is_sent_to_bki': ('ارسال به بازارگاه', lambda b: "بله" if b.is_sent_to_bki else "خیر"),
        'created_at': ('تاریخ ایجاد', lambda b: b.barnameh_created_at.strftime("%Y/%m/%d") if b.barnameh_created_at else "-"),
        'factor_sodoor_season': ('زمان صدور فاکتور فصل', lambda b: b.factor_sodoor_season or "-"),
        'is_factored': ('فاکتور صادر شده', lambda b: "بله" if b.is_factored else "خیر"),
        'is_created_by_excel': ('ایجاد توسط اکسل', lambda b: "بله" if b.is_created_by_excel else "خیر"),
        'factor_date': ('تاریخ ثبت فاکتور در سامانه مؤدیان', lambda b: b.factor_date.strftime("%Y/%m/%d") if b.factor_date else "-"),
        'is_sent_to_bki_at': ('تاریخ ارسال به بازارگاه', lambda b: b.is_sent_to_bki_at.strftime("%Y/%m/%d %H:%M") if b.is_sent_to_bki_at else "-"),
        'is_created_by_excel_at': ('تاریخ ایجاد توسط اکسل', lambda b: b.is_created_by_excel_at.strftime("%Y/%m/%d %H:%M") if hasattr(b, 'is_created_by_excel_at') and b.is_created_by_excel_at else "-"),
        'barnameh_updated_at': ('تاریخ بروزرسانی', lambda b: b.barnameh_updated_at.strftime("%Y/%m/%d %H:%M") if b.barnameh_updated_at else "-"),
    }
    
    # فقط ستون‌های انتخاب شده را اضافه می‌کنیم
    headers = []
    for col in selected_columns:
        if col in column_mapping:
            headers.append(column_mapping[col][0])
    
    # اضافه کردن ردیف اطلاعات گزارش
    info_row = [
        f"گزارش کامل بارنامه‌ها - تولید شده در {timezone.now().strftime('%Y/%m/%d %H:%M')}",
        "",  # سلول خالی
        f"تعداد کل: {queryset.count():,}",
        "",  # سلول خالی
    ]
    
    if from_date or to_date:
        date_range = f"از {from_date or 'ابتدا'} تا {to_date or 'انتها'}"
        info_row.extend(["", date_range])
    
    # اضافه کردن ردیف اطلاعات
    ws.append(info_row)
    
    # استایل ساده برای ردیف اطلاعات
    for i, cell in enumerate(ws[1], 1):
        cell.font = Font(bold=True)
        cell.alignment = alignment
    
    # اضافه کردن ردیف خالی
    ws.append([])
    
    # افزودن هدرها
    ws.append(headers)
    
    # تنظیم استایل برای سطر هدر
    header_row = ws.max_row
    for i, cell in enumerate(ws[header_row], 1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment
    
    # پردازش داده‌ها در batch برای بهینه‌سازی حافظه
    batch_size = 1000
    processed_count = 0
    
    # دریافت تمام داده‌ها به صورت iterator
    for barnameh in queryset.iterator(chunk_size=batch_size):
        row = []
        for col in selected_columns:
            if col in column_mapping:
                try:
                    value = column_mapping[col][1](barnameh)
                    row.append(value)
                except Exception as e:
                    logger.warning(f"خطا در استخراج مقدار {col} برای بارنامه {barnameh.id}: {str(e)}")
                    # برای فیلدهای عددی، مقدار پیش‌فرض 0 قرار می‌دهیم
                    if col in ['company_price', 'customer_price', 'total_sales_amount', 'total_purchase_amount', 'tonnage']:
                        row.append("0")
                    else:
                        row.append("-")
        
        ws.append(row)
        processed_count += 1
        
        # نمایش پیشرفت هر 1000 رکورد
        if processed_count % batch_size == 0:
            logger.info(f"پردازش شد: {processed_count:,} از {queryset.count():,} بارنامه")
        
        # تنظیم استایل برای سطرهای داده
        current_row = ws.max_row
        for j, cell in enumerate(ws[current_row], 1):
            cell.alignment = alignment
    
    logger.warning(f"تمام {processed_count:,} بارنامه پردازش شد")
    
    # تنظیم عرض ستون‌ها - ساده
    for i in range(1, len(headers) + 1):
        column_letter = ws.cell(row=header_row, column=i).column_letter
        ws.column_dimensions[column_letter].width = 12
    
    # اضافه کردن فریز به سطر هدر
    ws.freeze_panes = f"A{header_row + 1}"
    
    # تولید نام فایل
    current_time = timezone.now().strftime('%Y%m%d_%H%M%S')
    date_suffix = ""
    if from_date or to_date:
        date_suffix = f"_{from_date or 'start'}_to_{to_date or 'end'}"
    
    filename = f"barnameh_full_export{date_suffix}_{current_time}.xlsx"
    
    # تولید پاسخ HTTP
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    
    logger.warning(f"فایل اکسل کامل با موفقیت تولید شد: {filename}")
    return response