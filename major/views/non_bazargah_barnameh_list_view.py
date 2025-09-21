from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from bki_barnameh.models.BarnamehModel import Barnameh
from ERP.views.managers_profile_view import get_client_ip
import logging
import pandas as pd
from openpyxl import Workbook
import datetime
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Sum, Max, Min
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import jdatetime
from datetime import timedelta
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
from django.conf import settings

logger = logging.getLogger("major_non_bazargah_barnameh_list_view")

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

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def non_bazargah_barnameh_list(request):
    logger.warning(f"لیست بارنامه‌های خارج از بازارگاه توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # برای server-side filtering، فقط template خالی برمی‌گردانیم
    # داده‌ها از طریق AJAX API بارگذاری می‌شوند
    
    # دریافت ستون‌های قابل مشاهده از session کاربر
    default_visible_columns = [
        'select', 'number', 'serial', 'tonnage', 'driver_name', 'driver_phone', 
        'vehicle_plate', 'receiver_name', 'destination', 'barnameh_date', 
        'purchase_number', 'customer', 'product', 'buyer_name', 'actions'
    ]
    
    visible_columns = request.session.get('non_bazargah_barnameh_visible_columns', default_visible_columns)
    
    # اطمینان از وجود ستون‌های الزامی
    required_columns = ['select', 'actions']
    for req_col in required_columns:
        if req_col not in visible_columns:
            visible_columns.append(req_col)
    
    context = {
        'user_role': user_role,
        'total_barnamehs': 0,  # JavaScript این را بروزرسانی می‌کند
        'visible_columns': visible_columns,
    }
    
    return render(request, 'major/non_bazargah_barnameh_list.html', context)


def get_column_mapping():
    """
    نگاشت ستون‌ها به نام‌های فارسی برای خروجی اکسل
    """
    return {
        'select': 'انتخاب',
        'number': 'شماره بارنامه',
        'serial': 'سریال',
        'tonnage': 'وزن (کیلوگرم)',
        'driver_name': 'نام راننده',
        'driver_phone': 'شماره راننده',
        'vehicle_plate': 'پلاک خودرو',
        'receiver_name': 'نام گیرنده',
        'destination': 'مقصد',
        'barnameh_date': 'تاریخ بارنامه',
        'purchase_number': 'شماره خرید',
        'customer': 'مشتری',
        'product': 'محصول',
        'buyer_name': 'نام خریدار',
        'company_price': 'فی خرید (ریال)',
        'customer_price': 'فی فروش (ریال)',
        'total_sales_amount': 'مبلغ کل فروش',
        'total_purchase_amount': 'مبلغ کل خرید',
        'origin': 'مبدا',
        'rent': 'کرایه',
        'empty_vehicle_weight': 'وزن خالی ماشین',
        'loaded_vehicle_weight': 'وزن پر ماشین',
        'final_delivered_weight': 'وزن نهایی تحویل',
        'vehicle_arrival_time': 'زمان ورود ماشین',
        'empty_weigh_time': 'زمان وزن‌گیری خالی',
        'loaded_weigh_time': 'زمان وزن‌گیری پر',
        'departure_time': 'زمان خروج از انبار',
        'delivery_time': 'زمان تحویل',
        'actions': 'عملیات'
    }


def get_barnameh_data(barnameh, columns):
    """
    دریافت داده‌های بارنامه برای ستون‌های مشخص شده
    """
    column_mapping = get_column_mapping()
    data = {}
    
    for column in columns:
        if column == 'select':
            continue  # ستون انتخاب را نادیده بگیر
        elif column == 'number':
            data[column_mapping[column]] = barnameh.number or '-'
        elif column == 'serial':
            data[column_mapping[column]] = barnameh.serial or '-'
        elif column == 'tonnage':
            data[column_mapping[column]] = barnameh.tonnage or 0
        elif column == 'driver_name':
            data[column_mapping[column]] = barnameh.driver_name or '-'
        elif column == 'driver_phone':
            data[column_mapping[column]] = barnameh.driver_phone or '-'
        elif column == 'vehicle_plate':
            data[column_mapping[column]] = barnameh.vehicle_plate or '-'
        elif column == 'receiver_name':
            data[column_mapping[column]] = barnameh.receiver_name or '-'
        elif column == 'destination':
            data[column_mapping[column]] = barnameh.destination or '-'
        elif column == 'barnameh_date':
            data[column_mapping[column]] = barnameh.barnameh_date or '-'
        elif column == 'purchase_number':
            if barnameh.non_bazargah_purchase:
                data[column_mapping[column]] = barnameh.non_bazargah_purchase.purchase_number or '-'
            else:
                data[column_mapping[column]] = '-'
        elif column == 'customer':
            if barnameh.non_bazargah_purchase and barnameh.non_bazargah_purchase.customer:
                data[column_mapping[column]] = barnameh.non_bazargah_purchase.customer.name
            else:
                data[column_mapping[column]] = '-'
        elif column == 'product':
            if barnameh.non_bazargah_purchase and barnameh.non_bazargah_purchase.product:
                data[column_mapping[column]] = barnameh.non_bazargah_purchase.product.name
            else:
                data[column_mapping[column]] = '-'
        elif column == 'buyer_name':
            data[column_mapping[column]] = barnameh.get_buyer_name() or '-'
        elif column == 'company_price':
            data[column_mapping[column]] = barnameh.get_company_price() or 0
        elif column == 'customer_price':
            data[column_mapping[column]] = barnameh.get_customer_price() or 0
        elif column == 'total_sales_amount':
            data[column_mapping[column]] = barnameh.get_total_sales_amount() or 0
        elif column == 'total_purchase_amount':
            data[column_mapping[column]] = barnameh.get_total_purchase_amount() or 0
        elif column == 'origin':
            data[column_mapping[column]] = barnameh.origin or '-'
        elif column == 'rent':
            data[column_mapping[column]] = barnameh.rent or 0
        elif column == 'empty_vehicle_weight':
            data[column_mapping[column]] = barnameh.empty_vehicle_weight or '-'
        elif column == 'loaded_vehicle_weight':
            data[column_mapping[column]] = barnameh.loaded_vehicle_weight or '-'
        elif column == 'final_delivered_weight':
            data[column_mapping[column]] = barnameh.final_delivered_weight or '-'
        elif column == 'vehicle_arrival_time':
            data[column_mapping[column]] = barnameh.vehicle_arrival_time.strftime("%Y/%m/%d %H:%M") if barnameh.vehicle_arrival_time else '-'
        elif column == 'empty_weigh_time':
            data[column_mapping[column]] = barnameh.empty_weigh_time.strftime("%Y/%m/%d %H:%M") if barnameh.empty_weigh_time else '-'
        elif column == 'loaded_weigh_time':
            data[column_mapping[column]] = barnameh.loaded_weigh_time.strftime("%Y/%m/%d %H:%M") if barnameh.loaded_weigh_time else '-'
        elif column == 'departure_time':
            data[column_mapping[column]] = barnameh.departure_time.strftime("%Y/%m/%d %H:%M") if barnameh.departure_time else '-'
        elif column == 'delivery_time':
            data[column_mapping[column]] = barnameh.delivery_time.strftime("%Y/%m/%d %H:%M") if barnameh.delivery_time else '-'
        elif column == 'actions':
            continue  # ستون عملیات را نادیده بگیر
    
    return data


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def export_non_bazargah_barnamehs_excel(request):
    """
    خروجی اکسل از بارنامه‌های خارج از بازارگاه
    """
    logger.warning(f"خروجی اکسل از بارنامه‌های خارج از بازارگاه توسط {request.user.username} با آیپی {get_client_ip(request)}")
    
    try:
        # دریافت پارامترها
        ids_param = request.POST.get('ids', '')
        columns_param = request.POST.get('columns', '')
        
        # تبدیل پارامترها به لیست
        barnameh_ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()] if ids_param else []
        visible_columns = [col.strip() for col in columns_param.split(',') if col.strip()] if columns_param else []
        
        # ایجاد QuerySet
        base_queryset = Barnameh.objects.filter(
            type='Non_Bazargah'
        ).select_related(
            'non_bazargah_purchase', 'non_bazargah_purchase__customer', 
            'non_bazargah_purchase__unique_sales_agent', 'non_bazargah_purchase__product'
        ).prefetch_related(
            'non_bazargah_purchase__allocations'
        ).order_by('-barnameh_created_at')
        
        # فیلتر کردن بر اساس شناسه‌های انتخاب شده
        if barnameh_ids:
            base_queryset = base_queryset.filter(id__in=barnameh_ids)
        
        # اگر کاربر کارشناس فروش است، فقط بارنامه‌های مربوطه را ببیند
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(
                    non_bazargah_purchase__unique_sales_agent=request.user.sales_agent
                )
            else:
                base_queryset = Barnameh.objects.none()
        
        # دریافت بارنامه‌ها
        barnamehs = base_queryset
        
        if not barnamehs.exists():
            # اگر هیچ بارنامه‌ای وجود ندارد، فایل خالی برگردان
            wb = Workbook()
            ws = wb.active
            ws.title = 'بارنامه‌های خارج از بازارگاه'
            ws.cell(row=1, column=1, value='هیچ بارنامه‌ای یافت نشد')
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=non_bazargah_barnamehs_empty_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb.save(response)
            return response
        
        # ایجاد DataFrame
        data = []
        for barnameh in barnamehs:
            barnameh_data = get_barnameh_data(barnameh, visible_columns)
            data.append(barnameh_data)
        
        if not data:
            # اگر داده‌ای وجود ندارد، فایل خالی برگردان
            wb = Workbook()
            ws = wb.active
            ws.title = 'بارنامه‌های خارج از بازارگاه'
            ws.cell(row=1, column=1, value='هیچ داده‌ای برای نمایش وجود ندارد')
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=non_bazargah_barnamehs_empty_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb.save(response)
            return response
        
        df = pd.DataFrame(data)
        
        # ایجاد HTTP response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=non_bazargah_barnamehs_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        # ایجاد workbook و worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = 'بارنامه‌های خارج از بازارگاه'
        
        # اضافه کردن headers
        headers = list(df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
        
        # اضافه کردن داده‌ها
        for row_idx, row_data in enumerate(df.values, 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # ذخیره response
        wb.save(response)
        return response
        
    except Exception as e:
        logger.error(f"خطا در خروجی اکسل بارنامه‌های خارج از بازارگاه: {str(e)}")
        
        # در صورت خطا، فایل اکسل با پیام خطا برگردان
        wb = Workbook()
        ws = wb.active
        ws.title = 'خطا'
        ws.cell(row=1, column=1, value=f'خطا در ایجاد فایل اکسل: {str(e)}')
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
@require_POST
def apply_non_bazargah_barnameh_filter(request):
    """
    API برای اعمال فیلتر سمت سرور به بارنامه‌های خارج از بازارگاه
    """
    logger.warning(f"درخواست فیلتر بارنامه‌های خارج بازارگاه توسط {request.user.username} انجام شده.")
    
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        sort_config = json.loads(request.POST.get('sort', '{}'))
        page_param = request.POST.get('page', '1')
        per_page_param = request.POST.get('per_page', '25')
        global_search = request.POST.get('global_search', '').strip()
        
        try:
            page = int(page_param)
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            page = 1
            per_page = 25
        
        # ایجاد QuerySet پایه - فقط بارنامه‌های خارج از بازارگاه
        base_queryset = Barnameh.objects.filter(
            type='Non_Bazargah'
        ).select_related(
            'non_bazargah_purchase', 'non_bazargah_purchase__customer', 
            'non_bazargah_purchase__unique_sales_agent', 'non_bazargah_purchase__product'
        ).prefetch_related(
            'non_bazargah_purchase__allocations'
        ).order_by('-barnameh_date', '-barnameh_created_at')
        
        # اگر کاربر کارشناس فروش است، فقط بارنامه‌های مربوطه را ببیند
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(
                    non_bazargah_purchase__unique_sales_agent=request.user.sales_agent
                )
            else:
                base_queryset = Barnameh.objects.none()
        
        # اعمال فیلترها
        if filters:
            filter_conditions = Q()
            
            for column_id, filter_data in filters.items():
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if column_id == 'number':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(number__in=values)
                        else:
                            filter_conditions &= ~Q(number__in=values)
                            
                elif column_id == 'serial':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(serial__in=values)
                        else:
                            filter_conditions &= ~Q(serial__in=values)
                            
                elif column_id == 'tonnage':
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        numeric_values = list(set(numeric_values))  # حذف تکراری‌ها
                        if numeric_values:
                            if filter_type == 'include':
                                filter_conditions &= Q(tonnage__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(tonnage__in=numeric_values)
                    except (ValueError, TypeError):
                        continue
                        
                elif column_id == 'driver_name':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(driver_name__in=values)
                        else:
                            filter_conditions &= ~Q(driver_name__in=values)
                            
                elif column_id == 'driver_phone':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(driver_phone__in=values)
                        else:
                            filter_conditions &= ~Q(driver_phone__in=values)
                            
                elif column_id == 'vehicle_plate':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(vehicle_plate__in=values)
                        else:
                            filter_conditions &= ~Q(vehicle_plate__in=values)
                            
                elif column_id == 'receiver_name':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(receiver_name__in=values)
                        else:
                            filter_conditions &= ~Q(receiver_name__in=values)
                            
                elif column_id == 'destination':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(destination__in=values)
                        else:
                            filter_conditions &= ~Q(destination__in=values)
                            
                elif column_id == 'purchase_number':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(non_bazargah_purchase__purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(non_bazargah_purchase__purchase_number__in=values)
                            
                elif column_id == 'customer':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(non_bazargah_purchase__customer__name__in=values)
                        else:
                            filter_conditions &= ~Q(non_bazargah_purchase__customer__name__in=values)
                            
                elif column_id == 'product':
                    values = list(set([v for v in values if v and v.strip()]))  # حذف تکراری‌ها
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(non_bazargah_purchase__product__name__in=values)
                        else:
                            filter_conditions &= ~Q(non_bazargah_purchase__product__name__in=values)
                            
                elif column_id == 'barnameh_date':
                    try:
                        date_conditions = Q()
                        unique_dates = set([v for v in values if v and v.strip()])  # حذف تکراری‌ها
                        for date_str in unique_dates:
                            if '/' in date_str:
                                parts = date_str.split('/')
                                if len(parts) == 3:
                                    year, month, day = parts
                                    date_obj = datetime.datetime(int(year), int(month), int(day)).date()
                                    date_conditions |= Q(barnameh_date=date_obj)
                        
                        if date_conditions:
                            if filter_type == 'include':
                                filter_conditions &= date_conditions
                            else:
                                filter_conditions &= ~date_conditions
                    except (ValueError, TypeError):
                        continue
                        
                elif column_id in ['vehicle_arrival_time', 'empty_weigh_time', 'loaded_weigh_time', 'departure_time', 'delivery_time']:
                    try:
                        datetime_conditions = Q()
                        unique_datetimes = set([v for v in values if v and v.strip()])  # حذف تکراری‌ها
                        for datetime_str in unique_datetimes:
                            if '/' in datetime_str and ':' in datetime_str:
                                # فرمت: YYYY/MM/DD HH:MM
                                date_part, time_part = datetime_str.split(' ')
                                date_parts = date_part.split('/')
                                time_parts = time_part.split(':')
                                if len(date_parts) == 3 and len(time_parts) == 2:
                                    year, month, day = date_parts
                                    hour, minute = time_parts
                                    datetime_obj = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                                    datetime_conditions |= Q(**{column_id: datetime_obj})
                        
                        if datetime_conditions:
                            if filter_type == 'include':
                                filter_conditions &= datetime_conditions
                            else:
                                filter_conditions &= ~datetime_conditions
                    except (ValueError, TypeError):
                        continue
                
                else:
                    # برای فیلدهای دینامیک دیگر
                    try:
                        # بررسی اینکه آیا فیلد در مدل وجود دارد
                        field = Barnameh._meta.get_field(column_id)
                        values = [v for v in values if v and v.strip()]
                        
                        if values:
                            # تشخیص نوع فیلد و اعمال فیلتر متناسب
                            field_type = field.get_internal_type()
                            
                            if field_type == 'BooleanField':
                                # تبدیل مقادیر بولین و حذف تکراری‌ها
                                bool_values = set()
                                for v in values:
                                    if v.lower() in ['بله', 'true', '1', 'فعال']:
                                        bool_values.add(True)
                                    elif v.lower() in ['خیر', 'false', '0', 'غیرفعال']:
                                        bool_values.add(False)
                                
                                bool_values = list(bool_values)
                                if bool_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': bool_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': bool_values})
                            
                            elif field_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'FloatField', 'DecimalField']:
                                # تبدیل مقادیر عددی و حذف تکراری‌ها
                                numeric_values = set()
                                for v in values:
                                    try:
                                        cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                        if cleaned_value.replace('.', '').isdigit():
                                            numeric_values.add(float(cleaned_value))
                                    except:
                                        continue
                                
                                numeric_values = list(numeric_values)
                                if numeric_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': numeric_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': numeric_values})
                            
                            elif field_type in ['DateField', 'DateTimeField']:
                                # تبدیل مقادیر تاریخ و حذف تکراری‌ها
                                date_conditions = Q()
                                unique_dates = set([v for v in values if v and v.strip()])
                                for date_str in unique_dates:
                                    if '/' in date_str:
                                        parts = date_str.split('/')
                                        if len(parts) == 3:
                                            year, month, day = parts
                                            date_obj = datetime.datetime(int(year), int(month), int(day)).date()
                                            date_conditions |= Q(**{column_id: date_obj})
                                
                                if date_conditions:
                                    if filter_type == 'include':
                                        filter_conditions &= date_conditions
                                    else:
                                        filter_conditions &= ~date_conditions
                            
                            else:
                                # فیلتر متنی با حذف تکراری‌ها
                                unique_values = list(set([v for v in values if v and v.strip()]))
                                if unique_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': unique_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': unique_values})
                                    
                    except Exception as e:
                        logger.warning(f"خطا در اعمال فیلتر برای فیلد {column_id}: {e}")
                        continue
            
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
                Q(non_bazargah_purchase__purchase_number__icontains=global_search) |
                Q(non_bazargah_purchase__customer__name__icontains=global_search) |
                Q(non_bazargah_purchase__product__name__icontains=global_search)
            )
            base_queryset = base_queryset.filter(search_conditions).distinct()
        
        # اعمال مرتب‌سازی
        if sort_config and sort_config.get('column'):
            sort_column = sort_config['column']
            sort_direction = sort_config.get('direction', 'asc')
            
            sort_field_mapping = {
                'number': 'number',
                'serial': 'serial',
                'tonnage': 'tonnage',
                'driver_name': 'driver_name',
                'driver_phone': 'driver_phone',
                'vehicle_plate': 'vehicle_plate',
                'receiver_name': 'receiver_name',
                'destination': 'destination',
                'barnameh_date': 'barnameh_date',
                'purchase_number': 'non_bazargah_purchase__purchase_number',
                'customer': 'non_bazargah_purchase__customer__name',
                'product': 'non_bazargah_purchase__product__name',
            }
            
            # اگر فیلد در mapping موجود است، از آن استفاده کن، در غیر این صورت از خود نام فیلد
            sort_field = sort_field_mapping.get(sort_column, sort_column)
            
            # بررسی اینکه آیا فیلد برای مرتب‌سازی معتبر است
            try:
                if sort_column not in sort_field_mapping:
                    # بررسی اینکه آیا فیلد در مدل وجود دارد
                    Barnameh._meta.get_field(sort_column)
            except:
                # اگر فیلد وجود ندارد، از مرتب‌سازی پیش‌فرض استفاده کن
                sort_field = '-barnameh_created_at'
            
            if sort_direction == 'desc':
                sort_field = f'-{sort_field}'
            
            try:
                base_queryset = base_queryset.order_by(sort_field)
            except Exception as e:
                logger.warning(f"خطا در مرتب‌سازی: {e}")
                base_queryset = base_queryset.order_by('-barnameh_date', '-barnameh_created_at')
        else:
            base_queryset = base_queryset.order_by('-barnameh_created_at')
        
        # محاسبه تعداد کل قبل از pagination
        total_count = base_queryset.count()
        
        # اعمال pagination
        if per_page >= 10000:  # نمایش همه
            page_obj = base_queryset
            paginator = None
        else:
            paginator = Paginator(base_queryset, per_page)
            try:
                page_obj = paginator.page(page)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)
                page = 1
        
        # فرمت نتایج برای JSON response
        results = []
        for barnameh in page_obj:
            result = {
                'id': barnameh.id,
                'number': barnameh.number or '',
                'serial': barnameh.serial or '',
                'tonnage': barnameh.tonnage or 0,
                'driver_name': barnameh.driver_name or '',
                'driver_phone': barnameh.driver_phone or '',
                'vehicle_plate': barnameh.vehicle_plate or '',
                'receiver_name': barnameh.receiver_name or '',
                'destination': barnameh.destination or '',
                'barnameh_date': barnameh.barnameh_date.strftime("%Y/%m/%d") if barnameh.barnameh_date else '',
                'purchase_number': barnameh.non_bazargah_purchase.purchase_number if barnameh.non_bazargah_purchase else '',
                'customer': barnameh.non_bazargah_purchase.customer.name if barnameh.non_bazargah_purchase and barnameh.non_bazargah_purchase.customer else '',
                'product': barnameh.non_bazargah_purchase.product.name if barnameh.non_bazargah_purchase and barnameh.non_bazargah_purchase.product else '',
                'buyer_name': barnameh.get_buyer_name() or '',
                'company_price': barnameh.get_company_price() or 0,
                'customer_price': barnameh.get_customer_price() or 0,
                'total_sales_amount': barnameh.get_total_sales_amount() or 0,
                'total_purchase_amount': barnameh.get_total_purchase_amount() or 0,
                'origin': barnameh.origin or '',
                'rent': barnameh.rent or 0,
                'empty_vehicle_weight': barnameh.empty_vehicle_weight or '',
                'loaded_vehicle_weight': barnameh.loaded_vehicle_weight or '',
                'final_delivered_weight': barnameh.final_delivered_weight or '',
                'vehicle_arrival_time': barnameh.vehicle_arrival_time.strftime("%Y/%m/%d %H:%M") if barnameh.vehicle_arrival_time else '',
                'empty_weigh_time': barnameh.empty_weigh_time.strftime("%Y/%m/%d %H:%M") if barnameh.empty_weigh_time else '',
                'loaded_weigh_time': barnameh.loaded_weigh_time.strftime("%Y/%m/%d %H:%M") if barnameh.loaded_weigh_time else '',
                'departure_time': barnameh.departure_time.strftime("%Y/%m/%d %H:%M") if barnameh.departure_time else '',
                'delivery_time': barnameh.delivery_time.strftime("%Y/%m/%d %H:%M") if barnameh.delivery_time else '',
            }
            
            # اضافه کردن فیلدهای دینامیک از مدل
            try:
                for field in Barnameh._meta.get_fields():
                    if hasattr(barnameh, field.name) and field.name not in result:
                        value = getattr(barnameh, field.name, None)
                        if value is not None:
                            if hasattr(value, 'strftime'):  # تاریخ
                                result[field.name] = value.strftime('%Y/%m/%d')
                            elif isinstance(value, bool):  # بولین
                                result[field.name] = 'بله' if value else 'خیر'
                            else:
                                result[field.name] = str(value)
                        else:
                            result[field.name] = ''
            except Exception as e:
                logger.warning(f"خطا در اضافه کردن فیلدهای دینامیک: {e}")
            
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
        logger.error(f"خطا در اعمال فیلتر به بارنامه‌های خارج بازارگاه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در اعمال فیلتر: {str(e)}'
        }, status=500)


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
@require_POST
def get_non_bazargah_barnameh_column_values(request):
    """
    API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر بارنامه‌های خارج بازارگاه
    """
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        column_id = request.POST.get('column_id')
        search_term = request.POST.get('search', '')
        current_filters = request.POST.get('current_filters', '{}')
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
        base_queryset = Barnameh.objects.filter(
            type='Non_Bazargah'
        ).select_related(
            'non_bazargah_purchase', 'non_bazargah_purchase__customer', 
            'non_bazargah_purchase__unique_sales_agent', 'non_bazargah_purchase__product'
        ).prefetch_related(
            'non_bazargah_purchase__allocations'
        ).order_by('-barnameh_date', '-barnameh_created_at')
        
        # اگر کاربر کارشناس فروش است، فقط بارنامه‌های مربوطه را ببیند
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(
                    non_bazargah_purchase__unique_sales_agent=request.user.sales_agent
                )
            else:
                base_queryset = Barnameh.objects.none()
        
        # اعمال فیلترهای فعلی (بجز فیلتر ستون فعلی)
        if current_filters:
            filter_conditions = Q()
            
            for filter_column_id, filter_data in current_filters.items():
                if filter_column_id == column_id:
                    continue
                    
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                # اعمال فیلترهای مشابه تابع قبلی
                if filter_column_id == 'number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(number__in=values)
                        else:
                            filter_conditions &= ~Q(number__in=values)
                # ادامه فیلترها...
            
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
                Q(non_bazargah_purchase__purchase_number__icontains=global_search) |
                Q(non_bazargah_purchase__customer__name__icontains=global_search) |
                Q(non_bazargah_purchase__product__name__icontains=global_search)
            )
            base_queryset = base_queryset.filter(search_conditions).distinct()
        
        # دریافت مقادیر بر اساس نوع ستون
        values = []
        
        if column_id == 'number':
            values_qs = base_queryset.values_list('number', flat=True).distinct().exclude(number__isnull=True).exclude(number='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'serial':
            values_qs = base_queryset.values_list('serial', flat=True).distinct().exclude(serial__isnull=True).exclude(serial='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'tonnage':
            values_qs = base_queryset.values_list('tonnage', flat=True).distinct().exclude(tonnage__isnull=True)
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'driver_name':
            values_qs = base_queryset.values_list('driver_name', flat=True).distinct().exclude(driver_name__isnull=True).exclude(driver_name='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'driver_phone':
            values_qs = base_queryset.values_list('driver_phone', flat=True).distinct().exclude(driver_phone__isnull=True).exclude(driver_phone='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'vehicle_plate':
            values_qs = base_queryset.values_list('vehicle_plate', flat=True).distinct().exclude(vehicle_plate__isnull=True).exclude(vehicle_plate='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'receiver_name':
            values_qs = base_queryset.values_list('receiver_name', flat=True).distinct().exclude(receiver_name__isnull=True).exclude(receiver_name='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'destination':
            values_qs = base_queryset.values_list('destination', flat=True).distinct().exclude(destination__isnull=True).exclude(destination='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'barnameh_date':
            date_values = set()
            for barnameh in base_queryset:
                if barnameh.barnameh_date:
                    date_values.add(barnameh.barnameh_date.strftime("%Y/%m/%d"))
            values = sorted(list(date_values), reverse=True)  # تکراری‌ها از قبل حذف شده‌اند
            
        elif column_id == 'purchase_number':
            values_qs = base_queryset.filter(non_bazargah_purchase__isnull=False).values_list('non_bazargah_purchase__purchase_number', flat=True).distinct().exclude(non_bazargah_purchase__purchase_number__isnull=True).exclude(non_bazargah_purchase__purchase_number='')
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'customer':
            values_qs = base_queryset.filter(non_bazargah_purchase__customer__isnull=False).values_list('non_bazargah_purchase__customer__name', flat=True).distinct()
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'product':
            values_qs = base_queryset.filter(non_bazargah_purchase__product__isnull=False).values_list('non_bazargah_purchase__product__name', flat=True).distinct()
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'vehicle_arrival_time':
            time_values = set()
            for barnameh in base_queryset:
                if barnameh.vehicle_arrival_time:
                    time_values.add(barnameh.vehicle_arrival_time.strftime("%Y/%m/%d %H:%M"))
            values = sorted(list(time_values), reverse=True)
            
        elif column_id == 'empty_weigh_time':
            time_values = set()
            for barnameh in base_queryset:
                if barnameh.empty_weigh_time:
                    time_values.add(barnameh.empty_weigh_time.strftime("%Y/%m/%d %H:%M"))
            values = sorted(list(time_values), reverse=True)
            
        elif column_id == 'loaded_weigh_time':
            time_values = set()
            for barnameh in base_queryset:
                if barnameh.loaded_weigh_time:
                    time_values.add(barnameh.loaded_weigh_time.strftime("%Y/%m/%d %H:%M"))
            values = sorted(list(time_values), reverse=True)
            
        elif column_id == 'departure_time':
            time_values = set()
            for barnameh in base_queryset:
                if barnameh.departure_time:
                    time_values.add(barnameh.departure_time.strftime("%Y/%m/%d %H:%M"))
            values = sorted(list(time_values), reverse=True)
            
        elif column_id == 'delivery_time':
            time_values = set()
            for barnameh in base_queryset:
                if barnameh.delivery_time:
                    time_values.add(barnameh.delivery_time.strftime("%Y/%m/%d %H:%M"))
            values = sorted(list(time_values), reverse=True)
            
        elif column_id == 'empty_vehicle_weight':
            values_qs = base_queryset.values_list('empty_vehicle_weight', flat=True).distinct().exclude(empty_vehicle_weight__isnull=True)
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'loaded_vehicle_weight':
            values_qs = base_queryset.values_list('loaded_vehicle_weight', flat=True).distinct().exclude(loaded_vehicle_weight__isnull=True)
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
            
        elif column_id == 'final_delivered_weight':
            values_qs = base_queryset.values_list('final_delivered_weight', flat=True).distinct().exclude(final_delivered_weight__isnull=True)
            values = sorted(list(set(values_qs)))  # حذف تکراری‌ها و مرتب‌سازی
        
        else:
            # برای فیلدهای دینامیک دیگر
            try:
                # بررسی اینکه آیا فیلد در مدل وجود دارد
                field = Barnameh._meta.get_field(column_id)
                values_qs = base_queryset.values_list(column_id, flat=True).distinct().exclude(**{f'{column_id}__isnull': True})
                
                # فرمت کردن مقادیر بر اساس نوع فیلد
                formatted_values = set()  # استفاده از set برای جلوگیری از تکرار
                for value in values_qs:
                    if value is not None:
                        if hasattr(value, 'strftime'):  # تاریخ
                            formatted_values.add(value.strftime('%Y/%m/%d'))
                        elif isinstance(value, bool):  # بولین
                            formatted_values.add('بله' if value else 'خیر')
                        else:
                            formatted_values.add(str(value))
                
                values = sorted(list(formatted_values))  # تبدیل set به list مرتب شده
                
            except Exception as e:
                logger.warning(f"فیلد {column_id} در مدل یافت نشد یا خطا در دریافت مقادیر: {e}")
                values = []
        
        # فیلتر کردن بر اساس search_term و حذف تکراری‌های احتمالی
        if search_term:
            filtered_values = set()  # استفاده از set برای جلوگیری از تکرار
            for v in values:
                if search_term.lower() in str(v).lower():
                    filtered_values.add(v)
            values = sorted(list(filtered_values))
        
        # محدود کردن تعداد نتایج
        values = values[:100]
        
        return JsonResponse({
            'status': 'success',
            'values': values,
            'count': len(values)
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت مقادیر ستون بارنامه‌های خارج بازارگاه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت مقادیر: {str(e)}'
        }, status=500)


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def get_available_barnameh_fields(request):
    """
    API برای دریافت تمام فیلدهای قابل نمایش در جدول بارنامه‌های خارج بازارگاه
    """
    try:
        # تعریف فیلدهای پایه
        base_fields = [
            {'id': 'select', 'name': 'انتخاب', 'type': 'select', 'required': True},
            {'id': 'number', 'name': 'شماره بارنامه', 'type': 'text', 'required': False},
            {'id': 'serial', 'name': 'سریال', 'type': 'text', 'required': False},
            {'id': 'tonnage', 'name': 'وزن (کیلوگرم)', 'type': 'number', 'required': False},
            {'id': 'driver_name', 'name': 'نام راننده', 'type': 'text', 'required': False},
            {'id': 'driver_phone', 'name': 'شماره راننده', 'type': 'text', 'required': False},
            {'id': 'vehicle_plate', 'name': 'پلاک خودرو', 'type': 'text', 'required': False},
            {'id': 'receiver_name', 'name': 'نام گیرنده', 'type': 'text', 'required': False},
            {'id': 'destination', 'name': 'مقصد', 'type': 'text', 'required': False},
            {'id': 'barnameh_date', 'name': 'تاریخ بارنامه', 'type': 'date', 'required': False},
            {'id': 'purchase_number', 'name': 'شماره خرید', 'type': 'text', 'required': False},
            {'id': 'customer', 'name': 'مشتری', 'type': 'text', 'required': False},
            {'id': 'product', 'name': 'محصول', 'type': 'text', 'required': False},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'type': 'text', 'required': False},
            {'id': 'company_price', 'name': 'فی خرید (ریال)', 'type': 'number', 'required': False},
            {'id': 'customer_price', 'name': 'فی فروش (ریال)', 'type': 'number', 'required': False},
            {'id': 'total_sales_amount', 'name': 'مبلغ کل فروش', 'type': 'number', 'required': False},
            {'id': 'total_purchase_amount', 'name': 'مبلغ کل خرید', 'type': 'number', 'required': False},
            {'id': 'origin', 'name': 'مبدا', 'type': 'text', 'required': False},
            {'id': 'rent', 'name': 'کرایه', 'type': 'number', 'required': False},
            {'id': 'empty_vehicle_weight', 'name': 'وزن خالی ماشین', 'type': 'number', 'required': False},
            {'id': 'loaded_vehicle_weight', 'name': 'وزن پر ماشین', 'type': 'number', 'required': False},
            {'id': 'final_delivered_weight', 'name': 'وزن نهایی تحویل', 'type': 'number', 'required': False},
            {'id': 'vehicle_arrival_time', 'name': 'زمان ورود ماشین', 'type': 'datetime', 'required': False},
            {'id': 'empty_weigh_time', 'name': 'زمان وزن‌گیری خالی', 'type': 'datetime', 'required': False},
            {'id': 'loaded_weigh_time', 'name': 'زمان وزن‌گیری پر', 'type': 'datetime', 'required': False},
            {'id': 'departure_time', 'name': 'زمان خروج از انبار', 'type': 'datetime', 'required': False},
            {'id': 'delivery_time', 'name': 'زمان تحویل', 'type': 'datetime', 'required': False},
            {'id': 'actions', 'name': 'عملیات', 'type': 'actions', 'required': True},
        ]
        
        # فیلدهای اضافی که در آینده قابل اضافه کردن هستند
        extended_fields = []
        
        # بررسی فیلدهای موجود در مدل Barnameh
        try:
            model_fields = []
            for field in Barnameh._meta.get_fields():
                if not field.name.startswith('_') and field.name not in [f['id'] for f in base_fields]:
                    # اضافه کردن فیلدهای جدید از مدل
                    field_type = 'text'
                    if hasattr(field, 'get_internal_type'):
                        internal_type = field.get_internal_type()
                        if internal_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'FloatField', 'DecimalField']:
                            field_type = 'number'
                        elif internal_type in ['DateField', 'DateTimeField']:
                            field_type = 'date'
                        elif internal_type == 'BooleanField':
                            field_type = 'boolean'
                    
                    field_info = {
                        'id': field.name,
                        'name': getattr(field, 'verbose_name', field.name.replace('_', ' ').title()),
                        'type': field_type,
                        'required': False,
                        'is_model_field': True
                    }
                    model_fields.append(field_info)
            
            extended_fields.extend(model_fields)
        except Exception as e:
            logger.warning(f"خطا در دریافت فیلدهای مدل: {e}")
        
        # ترکیب فیلدهای پایه و اضافی
        all_fields = base_fields + extended_fields
        
        return JsonResponse({
            'status': 'success',
            'fields': all_fields,
            'base_fields_count': len(base_fields),
            'extended_fields_count': len(extended_fields)
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت فیلدهای قابل نمایش: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت فیلدها: {str(e)}'
        }, status=500)


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
@require_POST
def update_barnameh_table_columns(request):
    """
    API برای بروزرسانی ستون‌های نمایش داده شده در جدول
    """
    try:
        # دریافت لیست ستون‌های انتخاب شده
        visible_columns = request.POST.getlist('visible_columns[]')
        if not visible_columns:
            visible_columns = json.loads(request.POST.get('visible_columns', '[]'))
        
        # اطمینان از وجود ستون‌های الزامی
        required_columns = ['select', 'actions']
        for req_col in required_columns:
            if req_col not in visible_columns:
                visible_columns.append(req_col)
        
        # ذخیره تنظیمات در session کاربر
        request.session['non_bazargah_barnameh_visible_columns'] = visible_columns
        
        logger.info(f"ستون‌های جدول بارنامه‌های خارج بازارگاه برای کاربر {request.user.username} بروزرسانی شد: {visible_columns}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'تنظیمات ستون‌ها ذخیره شد',
            'visible_columns': visible_columns
        })
        
    except Exception as e:
        logger.error(f"خطا در بروزرسانی ستون‌های جدول: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در ذخیره تنظیمات: {str(e)}'
        }, status=500)


@csrf_exempt
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def export_full_non_bazargah_barnameh_excel(request):
    """
    خروجی اکسل کامل از همه بارنامه‌های خارج بازارگاه با تمام ستون‌ها و امکان انتخاب بازه تاریخ
    """
    logger.warning(f"خروجی اکسل کامل بارنامه‌های خارج بازارگاه توسط {request.user.username} با آی‌پی {get_client_ip(request)} آغاز شد")
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'فقط درخواست POST پذیرفته می‌شود'}, status=405)
    
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        # دریافت پارامترهای درخواست
        export_type = request.POST.get('export_type', 'all')
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        
        logger.warning(f"نوع خروجی: {export_type}, از تاریخ: {from_date}, تا تاریخ: {to_date}")
        
        # ایجاد QuerySet پایه - فقط بارنامه‌های خارج از بازارگاه
        base_queryset = Barnameh.objects.filter(
            type='Non_Bazargah'
        ).select_related(
            'non_bazargah_purchase', 'non_bazargah_purchase__customer', 
            'non_bazargah_purchase__unique_sales_agent', 'non_bazargah_purchase__product',
            'non_bazargah_allocation', 'non_bazargah_allocation__purchase'
        ).order_by('-barnameh_created_at')
        
        # اگر کاربر کارشناس فروش است، فقط بارنامه‌های مربوطه را ببیند
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(
                    non_bazargah_purchase__unique_sales_agent=request.user.sales_agent
                )
            else:
                base_queryset = Barnameh.objects.none()
        
        # اعمال فیلتر تاریخ اگر مشخص شده باشد - بر اساس barnameh_date
        if export_type == 'date_range' and (from_date or to_date):
            
            if from_date:
                try:
                    # تبدیل تاریخ شمسی به میلادی
                    from_date_obj = jalali_to_gregorian_date(from_date)
                    if from_date_obj:
                        # فیلتر روی barnameh_date (تاریخ بارنامه) - مهم‌تر از تاریخ ایجاد
                        base_queryset = base_queryset.filter(barnameh_date__gte=from_date_obj)
                        logger.info(f"فیلتر از تاریخ بارنامه شمسی {from_date} (میلادی: {from_date_obj}) اعمال شد")
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
                        # فیلتر روی barnameh_date (تاریخ بارنامه) - مهم‌تر از تاریخ ایجاد
                        base_queryset = base_queryset.filter(barnameh_date__lte=to_date_obj)
                        logger.info(f"فیلتر تا تاریخ بارنامه شمسی {to_date} (میلادی: {to_date_obj}) اعمال شد")
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
                'message': 'هیچ بارنامه‌ای در بازه انتخاب شده یافت نشد'
            }, status=400)
        
        # محدودیت تعداد برای جلوگیری از مشکلات عملکردی
        max_export_limit = 50000  # حداکثر 50,000 بارنامه
        if total_count > max_export_limit:
            return JsonResponse({
                'status': 'error',
                'message': f'تعداد بارنامه‌ها ({total_count:,}) بیش از حد مجاز ({max_export_limit:,}) است. لطفاً بازه تاریخی کوچک‌تری انتخاب کنید.'
            }, status=400)
        
        # تولید فایل اکسل
        return _export_non_bazargah_barnameh_excel_full(base_queryset, from_date, to_date)
        
    except Exception as e:
        import traceback
        logger.error(f"خطا در خروجی اکسل کامل بارنامه‌های خارج بازارگاه: {str(e)}, {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error', 
            'message': f'خطا در تولید فایل اکسل: {str(e)}'
        }, status=500)


def _export_non_bazargah_barnameh_excel_full(queryset, from_date=None, to_date=None):
    """پردازش و ایجاد فایل اکسل کامل برای همه بارنامه‌های خارج بازارگاه"""
    
    logger.warning(f"شروع تولید فایل اکسل کامل برای {queryset.count()} بارنامه خارج بازارگاه")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "بارنامه‌های خارج بازارگاه"
    
    # تنظیم گردش متن از راست به چپ
    ws.sheet_view.rightToLeft = True
    
    # استایل‌های ساده برای scalability
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')  # خاکستری ساده
    alignment = Alignment(horizontal='right', vertical='center')
    
    # مپینگ کامل ستون‌ها برای بارنامه‌های خارج بازارگاه
    column_mapping = {
        'number': ('شماره بارنامه', lambda b: b.number or "تعیین نشده"),
        'serial': ('سریال', lambda b: b.serial or "تعیین نشده"),
        'barnameh_date': ('تاریخ بارنامه', lambda b: b.barnameh_date.strftime("%Y/%m/%d") if b.barnameh_date else "-"),
        'driver_name': ('نام راننده', lambda b: b.driver_name or "-"),
        'driver_phone': ('تلفن راننده', lambda b: b.driver_phone or "-"),
        'vehicle_plate': ('پلاک', lambda b: b.vehicle_plate or "-"),
        'tonnage': ('وزن (کیلوگرم)', lambda b: f"{int(b.tonnage)}" if b.tonnage else "0"),
        'receiver_name': ('نام گیرنده', lambda b: b.receiver_name or "-"),
        'destination': ('مقصد', lambda b: b.destination or "-"),
        'purchase_number': ('شماره خرید', lambda b: b.non_bazargah_purchase.purchase_number if b.non_bazargah_purchase else "-"),
        'customer': ('مشتری', lambda b: b.non_bazargah_purchase.customer.name if b.non_bazargah_purchase and b.non_bazargah_purchase.customer else "-"),
        'product': ('محصول', lambda b: b.non_bazargah_purchase.product.name if b.non_bazargah_purchase and b.non_bazargah_purchase.product else "-"),
        'buyer_name': ('نام خریدار', lambda b: b.get_buyer_name() or "-"),
        'company_price': ('فی خرید (ریال)', lambda b: f"{b.get_company_price():,}" if b.get_company_price() and b.get_company_price() > 0 else "0"),
        'customer_price': ('فی فروش (ریال)', lambda b: f"{b.get_customer_price():,}" if b.get_customer_price() and b.get_customer_price() > 0 else "0"),
        'total_sales_amount': ('مبلغ کل فروش', lambda b: f"{b.get_total_sales_amount():,.0f}" if b.get_total_sales_amount() else "-"),
        'total_purchase_amount': ('مبلغ کل خرید', lambda b: f"{b.get_total_purchase_amount():,.0f}" if b.get_total_purchase_amount() and b.get_total_purchase_amount() > 0 else "0"),
        'origin': ('مبدا', lambda b: b.origin or "-"),
        'rent': ('کرایه', lambda b: f"{b.rent:,}" if b.rent else "0"),
        'empty_vehicle_weight': ('وزن خالی ماشین', lambda b: f"{b.empty_vehicle_weight}" if b.empty_vehicle_weight else "-"),
        'loaded_vehicle_weight': ('وزن پر ماشین', lambda b: f"{b.loaded_vehicle_weight}" if b.loaded_vehicle_weight else "-"),
        'final_delivered_weight': ('وزن نهایی تحویل', lambda b: f"{b.final_delivered_weight}" if b.final_delivered_weight else "-"),
        'vehicle_arrival_time': ('زمان ورود ماشین', lambda b: b.vehicle_arrival_time.strftime("%Y/%m/%d %H:%M") if b.vehicle_arrival_time else "-"),
        'empty_weigh_time': ('زمان وزن خالی', lambda b: b.empty_weigh_time.strftime("%Y/%m/%d %H:%M") if b.empty_weigh_time else "-"),
        'loading_start_time': ('شروع بارگیری', lambda b: b.loading_start_time.strftime("%Y/%m/%d %H:%M") if b.loading_start_time else "-"),
        'loading_end_time': ('پایان بارگیری', lambda b: b.loading_end_time.strftime("%Y/%m/%d %H:%M") if b.loading_end_time else "-"),
        'loaded_weigh_time': ('زمان وزن پر', lambda b: b.loaded_weigh_time.strftime("%Y/%m/%d %H:%M") if b.loaded_weigh_time else "-"),
        'departure_time': ('زمان خروج از انبار', lambda b: b.departure_time.strftime("%Y/%m/%d %H:%M") if b.departure_time else "-"),
        'delivery_time': ('زمان تحویل', lambda b: b.delivery_time.strftime("%Y/%m/%d %H:%M") if b.delivery_time else "-"),
        'factor_date': ('تاریخ ثبت فاکتور', lambda b: b.factor_date.strftime("%Y/%m/%d") if b.factor_date else "-"),
        'created_at': ('تاریخ ایجاد', lambda b: b.barnameh_created_at.strftime("%Y/%m/%d %H:%M") if b.barnameh_created_at else "-"),
        'updated_at': ('تاریخ بروزرسانی', lambda b: b.barnameh_updated_at.strftime("%Y/%m/%d %H:%M") if b.barnameh_updated_at else "-"),
        'sales_agent': ('کارشناس فروش', lambda b: b.non_bazargah_purchase.unique_sales_agent.name if b.non_bazargah_purchase and b.non_bazargah_purchase.unique_sales_agent else "-"),
        'net_cargo_weight': ('وزن خالص بار', lambda b: f"{b.get_net_cargo_weight()}" if b.get_net_cargo_weight() else "-"),
        'weight_difference_from_order': ('اختلاف وزن با سفارش', lambda b: f"{b.get_weight_difference_from_order()}" if b.get_weight_difference_from_order() is not None else "-"),
        'loading_duration': ('مدت بارگیری', lambda b: str(b.get_loading_duration()) if b.get_loading_duration() else "-"),
    }
    
    # همه ستون‌ها را اضافه می‌کنیم
    all_columns = list(column_mapping.keys())
    headers = [column_mapping[col][0] for col in all_columns]
    
    # اضافه کردن ردیف اطلاعات گزارش
    info_row = [
        f"گزارش کامل بارنامه‌های خارج بازارگاه - تولید شده در {timezone.now().strftime('%Y/%m/%d %H:%M')}",
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
        for col in all_columns:
            try:
                value = column_mapping[col][1](barnameh)
                row.append(value)
            except Exception as e:
                logger.warning(f"خطا در استخراج مقدار {col} برای بارنامه {barnameh.id}: {str(e)}")
                # برای فیلدهای عددی، مقدار پیش‌فرض 0 قرار می‌دهیم
                if col in ['company_price', 'customer_price', 'total_sales_amount', 'total_purchase_amount', 'tonnage', 'rent']:
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
        ws.column_dimensions[column_letter].width = 15
    
    # اضافه کردن فریز به سطر هدر
    ws.freeze_panes = f"A{header_row + 1}"
    
    # تولید نام فایل
    current_time = timezone.now().strftime('%Y%m%d_%H%M%S')
    date_suffix = ""
    if from_date or to_date:
        date_suffix = f"_{from_date or 'start'}_to_{to_date or 'end'}"
    
    filename = f"non_bazargah_barnamehs_full_export{date_suffix}_{current_time}.xlsx"
    
    # تولید پاسخ HTTP
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    
    logger.warning(f"فایل اکسل کامل بارنامه‌های خارج بازارگاه با موفقیت تولید شد: {filename}")
    return response


@role_required('admin', 'logistics_manager')
@login_required
def fast_non_bazargah_barnameh_report_pdf(request):
    """
    گزارش PDF از خریدهای خارج بازارگاه 7 روز اخیر که بارنامه سریع (کمتر از 3 روز) دارند
    به تفکیک کارشناس فروش - با پشتیبانی کامل از فارسی
    """
    try:
        from major.models.NonBazargahPurchase import NonBazargahPurchase
        from core.SalesAgentModel import SalesAgent
        from django.db.models import Prefetch
        
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
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
                # فقط عدد را فرمت کن، بدون پردازش فارسی
                return f"{int(value):,}"
            except (ValueError, TypeError):
                return default
        
        # تابع کمکی برای فرمت کردن اعداد با واحد
        def format_number_with_unit(value, unit_text, default='0'):
            """تبدیل اعداد با واحد به متن مناسب"""
            if value is None or value == 0:
                return default
            try:
                number_part = f"{int(value):,}"
                if unit_text:
                    # برای واحدها، عدد و واحد را جداگانه پردازش کن
                    unit_processed = process_persian_text(unit_text)
                    return f"{number_part} {unit_processed}"
                else:
                    return number_part
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
        seven_days_ago = now - timedelta(days=7)
        
        logger.info(f"گزارش بارنامه‌های سریع خارج بازارگاه از {seven_days_ago} تا {now}")
        
        # یافتن بارنامه‌های خارج بازارگاه 7 روز اخیر بر اساس barnameh_date
        recent_barnamehs = Barnameh.objects.filter(
            type='Non_Bazargah',
            barnameh_date__gte=seven_days_ago.date()
        ).select_related(
            'non_bazargah_purchase', 'non_bazargah_purchase__customer', 
            'non_bazargah_purchase__unique_sales_agent', 'non_bazargah_purchase__product',
            'non_bazargah_allocation'
        )
        
        # اگر کاربر کارشناس فروش است، فقط بارنامه‌های مربوطه را ببیند
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                recent_barnamehs = recent_barnamehs.filter(
                    non_bazargah_purchase__unique_sales_agent=request.user.sales_agent
                )
            else:
                recent_barnamehs = Barnameh.objects.none()
        
        # یافتن بارنامه‌های سریع (کمتر از 3 روز) بر اساس barnameh_date
        fast_purchases = []
        
        for barnameh in recent_barnamehs:
            if barnameh.barnameh_date and barnameh.non_bazargah_purchase:
                # محاسبه تفاوت زمان بین ثبت خرید و تاریخ بارنامه
                purchase_date = barnameh.non_bazargah_purchase.created_at.date()
                barnameh_date = barnameh.barnameh_date
                
                # محاسبه تفاوت روز
                actual_days_diff = (barnameh_date - purchase_date).days
                
                if actual_days_diff <= 3:  # کمتر از 3 روز
                    # تشخیص نوع ارتباط (مستقیم یا از طریق تخصیص)
                    allocation = barnameh.non_bazargah_allocation
                    
                    fast_purchases.append({
                        'purchase': barnameh.non_bazargah_purchase,
                        'barnameh': barnameh,
                        'days_diff': actual_days_diff,
                        'allocation': allocation
                    })
        
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
        filename = f"fast_non_bazargah_barnameh_report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
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
            story.append(Paragraph(process_persian_text("گزارش بارنامه‌های سریع خارج بازارگاه"), title_style))
            story.append(Spacer(1, 20))
            story.append(Paragraph(process_persian_text("هیچ خرید خارج بازارگاه با بارنامه سریع در 7 روز اخیر یافت نشد."), normal_style))
            
            doc.build(story)
            pdf = buffer.getvalue()
            buffer.close()
            response.write(pdf)
            return response
        
        # تاریخ‌های شمسی
        import jdatetime
        jalali_start = jdatetime.datetime.fromgregorian(datetime=seven_days_ago).strftime('%Y/%m/%d')
        jalali_end = jdatetime.datetime.fromgregorian(datetime=now).strftime('%Y/%m/%d')
        
        # برای هر کارشناس فروش صفحه کاملاً جداگانه
        first_page = True
        for agent_key, agent_data in sales_agent_groups.items():
            if not first_page:  # اگر اولین صفحه نیست، صفحه جدید بساز
                story.append(PageBreak())
            first_page = False
            
            # عنوان اصلی گزارش برای هر کارشناس
            story.append(Paragraph(process_persian_text("گزارش خریدهای خارج بازارگاه دارای بارنامه سریع"), title_style))
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
                purchase_title = f"خرید خارج بازارگاه شماره: {purchase.purchase_number or 'نامشخص'}"
                story.append(Paragraph(process_persian_text(purchase_title), subtitle_style))
                story.append(Spacer(1, 8))
                
                # اطلاعات کلی خرید خارج بازارگاه
                purchase_info_data = [
                    [
                        process_persian_text('مقدار خرید'),
                        process_persian_text('نام مشتری'),
                        process_persian_text('محصول'),
                        process_persian_text('تعداد بارنامه‌های سریع')
                    ],
                    [
                        format_number_with_unit(purchase.quantity, purchase.get_unit_display() if purchase.unit else None) if purchase.quantity else "-",
                        process_persian_text(purchase.customer.name) if purchase.customer and purchase.customer.name else "-",
                        process_persian_text(purchase.product.name) if purchase.product and purchase.product.name else "-",
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
                        process_persian_text('نوع ارتباط'),
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
                    allocation = item['allocation']
                    
                    # تشخیص نوع ارتباط (مستقیم یا از طریق تخصیص)
                    relation_type = "تخصیص" if allocation else "مستقیم"
                    
                    barnameh_number = safe_text(barnameh.number)
                    serial_text = safe_text(barnameh.serial)
                    tonnage_text = format_number_with_unit(barnameh.tonnage, "کیلوگرم") if barnameh.tonnage else "-"
                    driver_name = process_persian_text(barnameh.driver_name) if barnameh.driver_name else "-"
                    driver_phone = safe_text(barnameh.driver_phone) if barnameh.driver_phone else "-"
                    plate_text = safe_text(barnameh.vehicle_plate) if barnameh.vehicle_plate else "-"
                    days_diff = f"{item['days_diff']}"
                    
                    barnameh_table_data.append([
                        process_persian_text(str(idx)),
                        process_persian_text(relation_type),
                        barnameh_number,
                        serial_text,
                        tonnage_text,
                        driver_name,
                        driver_phone,
                        plate_text,
                        days_diff
                    ])
                
                barnameh_table = Table(barnameh_table_data, colWidths=[15*mm, 20*mm, 25*mm, 20*mm, 20*mm, 25*mm, 25*mm, 20*mm, 15*mm])
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
        
        logger.info(f"گزارش PDF بارنامه‌های سریع خارج بازارگاه با پشتیبانی فارسی ایجاد شد: {filename}")
        return response
        
    except Exception as e:
        logger.error(f"خطا در ایجاد گزارش PDF بارنامه‌های سریع خارج بازارگاه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در ایجاد گزارش: {str(e)}'
        }, status=500)

