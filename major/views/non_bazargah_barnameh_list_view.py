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

logger = logging.getLogger("major_non_bazargah_barnameh_list_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def non_bazargah_barnameh_list(request):
    logger.warning(f"لیست بارنامه‌های خارج از بازارگاه توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
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

    # تنظیم pagination ساده
    paginator = Paginator(base_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        'barnamehs': page_obj,
        'user_role': user_role,
        'total_barnamehs': paginator.count,
        'paginator': paginator,
        'page_obj': page_obj,
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

