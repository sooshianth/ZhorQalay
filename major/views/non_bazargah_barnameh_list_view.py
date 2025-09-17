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

logger = logging.getLogger("major_non_bazargah_barnameh_list_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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
            data[column_mapping[column]] = barnameh.vehicle_arrival_time or '-'
        elif column == 'departure_time':
            data[column_mapping[column]] = barnameh.departure_time or '-'
        elif column == 'delivery_time':
            data[column_mapping[column]] = barnameh.delivery_time or '-'
        elif column == 'actions':
            continue  # ستون عملیات را نادیده بگیر
    
    return data


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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
        ).order_by('-barnameh_created_at')
        
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
                            
                elif column_id == 'tonnage':
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
                        
                elif column_id == 'driver_name':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(driver_name__in=values)
                        else:
                            filter_conditions &= ~Q(driver_name__in=values)
                            
                elif column_id == 'driver_phone':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(driver_phone__in=values)
                        else:
                            filter_conditions &= ~Q(driver_phone__in=values)
                            
                elif column_id == 'vehicle_plate':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(vehicle_plate__in=values)
                        else:
                            filter_conditions &= ~Q(vehicle_plate__in=values)
                            
                elif column_id == 'receiver_name':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(receiver_name__in=values)
                        else:
                            filter_conditions &= ~Q(receiver_name__in=values)
                            
                elif column_id == 'destination':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(destination__in=values)
                        else:
                            filter_conditions &= ~Q(destination__in=values)
                            
                elif column_id == 'purchase_number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(non_bazargah_purchase__purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(non_bazargah_purchase__purchase_number__in=values)
                            
                elif column_id == 'customer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(non_bazargah_purchase__customer__name__in=values)
                        else:
                            filter_conditions &= ~Q(non_bazargah_purchase__customer__name__in=values)
                            
                elif column_id == 'product':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(non_bazargah_purchase__product__name__in=values)
                        else:
                            filter_conditions &= ~Q(non_bazargah_purchase__product__name__in=values)
                            
                elif column_id == 'barnameh_date':
                    try:
                        date_conditions = Q()
                        for date_str in values:
                            if date_str and date_str.strip():
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
                                # تبدیل مقادیر بولین
                                bool_values = []
                                for v in values:
                                    if v.lower() in ['بله', 'true', '1', 'فعال']:
                                        bool_values.append(True)
                                    elif v.lower() in ['خیر', 'false', '0', 'غیرفعال']:
                                        bool_values.append(False)
                                
                                if bool_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': bool_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': bool_values})
                            
                            elif field_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'FloatField', 'DecimalField']:
                                # تبدیل مقادیر عددی
                                numeric_values = []
                                for v in values:
                                    try:
                                        cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                        if cleaned_value.replace('.', '').isdigit():
                                            numeric_values.append(float(cleaned_value))
                                    except:
                                        continue
                                
                                if numeric_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': numeric_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': numeric_values})
                            
                            elif field_type in ['DateField', 'DateTimeField']:
                                # تبدیل مقادیر تاریخ
                                date_conditions = Q()
                                for date_str in values:
                                    if date_str and date_str.strip():
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
                                # فیلتر متنی
                                if filter_type == 'include':
                                    filter_conditions &= Q(**{f'{column_id}__in': values})
                                else:
                                    filter_conditions &= ~Q(**{f'{column_id}__in': values})
                                    
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
                base_queryset = base_queryset.order_by('-barnameh_created_at')
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


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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
        )
        
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
            values = list(values_qs)
            
        elif column_id == 'serial':
            values_qs = base_queryset.values_list('serial', flat=True).distinct().exclude(serial__isnull=True).exclude(serial='')
            values = list(values_qs)
            
        elif column_id == 'tonnage':
            values_qs = base_queryset.values_list('tonnage', flat=True).distinct().exclude(tonnage__isnull=True)
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'driver_name':
            values_qs = base_queryset.values_list('driver_name', flat=True).distinct().exclude(driver_name__isnull=True).exclude(driver_name='')
            values = list(values_qs)
            
        elif column_id == 'driver_phone':
            values_qs = base_queryset.values_list('driver_phone', flat=True).distinct().exclude(driver_phone__isnull=True).exclude(driver_phone='')
            values = list(values_qs)
            
        elif column_id == 'vehicle_plate':
            values_qs = base_queryset.values_list('vehicle_plate', flat=True).distinct().exclude(vehicle_plate__isnull=True).exclude(vehicle_plate='')
            values = list(values_qs)
            
        elif column_id == 'receiver_name':
            values_qs = base_queryset.values_list('receiver_name', flat=True).distinct().exclude(receiver_name__isnull=True).exclude(receiver_name='')
            values = list(values_qs)
            
        elif column_id == 'destination':
            values_qs = base_queryset.values_list('destination', flat=True).distinct().exclude(destination__isnull=True).exclude(destination='')
            values = list(values_qs)
            
        elif column_id == 'barnameh_date':
            date_values = set()
            for barnameh in base_queryset:
                if barnameh.barnameh_date:
                    date_values.add(barnameh.barnameh_date.strftime("%Y/%m/%d"))
            values = sorted(list(date_values), reverse=True)
            
        elif column_id == 'purchase_number':
            values_qs = base_queryset.filter(non_bazargah_purchase__isnull=False).values_list('non_bazargah_purchase__purchase_number', flat=True).distinct().exclude(non_bazargah_purchase__purchase_number__isnull=True).exclude(non_bazargah_purchase__purchase_number='')
            values = list(values_qs)
            
        elif column_id == 'customer':
            values_qs = base_queryset.filter(non_bazargah_purchase__customer__isnull=False).values_list('non_bazargah_purchase__customer__name', flat=True).distinct()
            values = list(values_qs)
            
        elif column_id == 'product':
            values_qs = base_queryset.filter(non_bazargah_purchase__product__isnull=False).values_list('non_bazargah_purchase__product__name', flat=True).distinct()
            values = list(values_qs)
        
        else:
            # برای فیلدهای دینامیک دیگر
            try:
                # بررسی اینکه آیا فیلد در مدل وجود دارد
                field = Barnameh._meta.get_field(column_id)
                values_qs = base_queryset.values_list(column_id, flat=True).distinct().exclude(**{f'{column_id}__isnull': True})
                
                # فرمت کردن مقادیر بر اساس نوع فیلد
                formatted_values = []
                for value in values_qs:
                    if value is not None:
                        if hasattr(value, 'strftime'):  # تاریخ
                            formatted_values.append(value.strftime('%Y/%m/%d'))
                        elif isinstance(value, bool):  # بولین
                            formatted_values.append('بله' if value else 'خیر')
                        else:
                            formatted_values.append(str(value))
                
                values = list(set(formatted_values))  # حذف تکراری‌ها
                
            except Exception as e:
                logger.warning(f"فیلد {column_id} در مدل یافت نشد یا خطا در دریافت مقادیر: {e}")
                values = []
        
        # فیلتر کردن بر اساس search_term
        if search_term:
            values = [v for v in values if search_term.lower() in str(v).lower()]
        
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


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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

