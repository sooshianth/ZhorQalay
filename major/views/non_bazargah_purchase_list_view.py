from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from major.models.NonBazargahPurchase import NonBazargahPurchase
from ERP.views.managers_profile_view import get_client_ip
import logging
import pandas as pd
from openpyxl import Workbook
import datetime

logger = logging.getLogger("major_non_bazargah_purchase_list_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def non_bazargah_purchase_list(request):
    logger.warning(f"لیست خریدهای خارج از بازارگاه توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # ایجاد QuerySet پایه
    base_queryset = NonBazargahPurchase.objects.select_related(
        'customer', 'unique_sales_agent', 'product'
    ).prefetch_related('phishes').order_by('-created_at')
    
    # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
    if user_role == 'sales_agent':
        if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
            base_queryset = base_queryset.filter(unique_sales_agent=request.user.sales_agent)
        else:
            base_queryset = NonBazargahPurchase.objects.none()

    # تنظیم pagination ساده
    paginator = Paginator(base_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        'purchases': page_obj,
        'user_role': user_role,
        'total_purchases': paginator.count,
        'paginator': paginator,
        'page_obj': page_obj,
    }
    
    return render(request, 'major/non_bazargah_purchase_list.html', context)


def get_column_mapping():
    """
    نگاشت ستون‌ها به نام‌های فارسی برای خروجی اکسل
    """
    return {
        'select': 'انتخاب',
        'purchase_number': 'شماره خرید',
        'created_at': 'تاریخ',
        'unique_sales_agent': 'نماینده فروش',
        'total_weight': 'وزن (کیلوگرم)',
        'state': 'وضعیت',
        'product': 'محصول',
        'unit': 'واحد',
        'customer': 'مشتری',
        'buyer_name': 'نام خریدار',
        'customer_price': 'فی فروش (ریال)',
        'quantity': 'مقدار',
        'bag_weight': 'وزن کیسه',
        'empty_weight': 'وزن خالی',
        'loaded_weight': 'وزن پر',
        'delivered_weight': 'وزن تحویلی',
        'weight_difference': 'اختلاف وزن',
        'amount_paid': 'مبلغ پرداختی',
        'payment_verified_by': 'تایید شده توسط',
        'payment_verified_at': 'زمان تایید',
        'warehouse_contact_person': 'رابط انبار',
        'warehouse_contact_phone': 'تماس انبار',
        'logistics_notes': 'یادداشت لجستیک',
        'phish_accounts': 'شماره حساب‌های استفاده شده',
        'phish_count': 'تعداد فیش‌ها',
        'total_phish_amount': 'مجموع فیش‌ها (ریال)',
        'actions': 'عملیات'
    }


def get_purchase_data(purchase, columns):
    """
    دریافت داده‌های خرید برای ستون‌های مشخص شده
    """
    column_mapping = get_column_mapping()
    data = {}
    
    for column in columns:
        if column == 'select':
            continue  # ستون انتخاب را نادیده بگیر
        elif column == 'purchase_number':
            data[column_mapping[column]] = purchase.purchase_number or '-'
        elif column == 'created_at':
            data[column_mapping[column]] = purchase.created_at.strftime('%Y/%m/%d') if purchase.created_at else '-'
        elif column == 'unique_sales_agent':
            data[column_mapping[column]] = purchase.unique_sales_agent.name if purchase.unique_sales_agent else '-'
        elif column == 'total_weight':
            data[column_mapping[column]] = purchase.total_weight or 0
        elif column == 'state':
            data[column_mapping[column]] = purchase.get_state_display() if hasattr(purchase, 'get_state_display') else purchase.state
        elif column == 'product':
            data[column_mapping[column]] = purchase.product.name if purchase.product else '-'
        elif column == 'unit':
            data[column_mapping[column]] = purchase.get_unit_display() if hasattr(purchase, 'get_unit_display') else purchase.unit
        elif column == 'customer':
            data[column_mapping[column]] = purchase.customer.name if purchase.customer else '-'
        elif column == 'buyer_name':
            data[column_mapping[column]] = purchase.buyer_name or '-'
        elif column == 'customer_price':
            data[column_mapping[column]] = purchase.customer_price or 0
        elif column == 'quantity':
            data[column_mapping[column]] = purchase.quantity or '-'
        elif column == 'bag_weight':
            data[column_mapping[column]] = purchase.bag_weight or '-'
        elif column == 'empty_weight':
            data[column_mapping[column]] = purchase.empty_weight or '-'
        elif column == 'loaded_weight':
            data[column_mapping[column]] = purchase.loaded_weight or '-'
        elif column == 'delivered_weight':
            data[column_mapping[column]] = purchase.delivered_weight or '-'
        elif column == 'weight_difference':
            data[column_mapping[column]] = purchase.weight_difference or '-'
        elif column == 'amount_paid':
            data[column_mapping[column]] = purchase.amount_paid or 0
        elif column == 'payment_verified_by':
            data[column_mapping[column]] = purchase.payment_verified_by.username if purchase.payment_verified_by else '-'
        elif column == 'payment_verified_at':
            data[column_mapping[column]] = purchase.payment_verified_at.strftime('%Y/%m/%d %H:%M') if purchase.payment_verified_at else '-'
        elif column == 'warehouse_contact_person':
            data[column_mapping[column]] = purchase.warehouse_contact_person or '-'
        elif column == 'warehouse_contact_phone':
            data[column_mapping[column]] = purchase.warehouse_contact_phone or '-'
        elif column == 'logistics_notes':
            data[column_mapping[column]] = purchase.logistics_notes or '-'
        elif column == 'phish_accounts':
            # دریافت لیست شماره حساب‌های استفاده شده در فیش‌ها
            accounts = []
            for phish in purchase.phishes.all():
                account_info = f"{phish.bank_name} - {phish.account_number}"
                if account_info not in accounts:
                    accounts.append(account_info)
            data[column_mapping[column]] = ', '.join(accounts) if accounts else '-'
        elif column == 'phish_count':
            data[column_mapping[column]] = purchase.phishes.count()
        elif column == 'total_phish_amount':
            data[column_mapping[column]] = purchase.get_total_phish_amount() if hasattr(purchase, 'get_total_phish_amount') else 0
        elif column == 'actions':
            continue  # ستون عملیات را نادیده بگیر
    
    return data


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def export_non_bazargah_purchases_excel(request):
    """
    خروجی اکسل از خریدهای خارج از بازارگاه
    """
    logger.warning(f"خروجی اکسل از خریدهای خارج از بازارگاه توسط {request.user.username} با آیپی {get_client_ip(request)}")
    
    try:
        # دریافت پارامترها
        ids_param = request.POST.get('ids', '')
        columns_param = request.POST.get('columns', '')
        
        # تبدیل پارامترها به لیست
        purchase_ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()] if ids_param else []
        visible_columns = [col.strip() for col in columns_param.split(',') if col.strip()] if columns_param else []
        
        # ایجاد QuerySet
        base_queryset = NonBazargahPurchase.objects.select_related(
            'customer', 'unique_sales_agent', 'product'
        ).prefetch_related('phishes').order_by('-created_at')
        
        # فیلتر کردن بر اساس شناسه‌های انتخاب شده
        if purchase_ids:
            base_queryset = base_queryset.filter(id__in=purchase_ids)
        
        # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(unique_sales_agent=request.user.sales_agent)
            else:
                base_queryset = NonBazargahPurchase.objects.none()
        
        # دریافت خریدها
        purchases = base_queryset
        
        if not purchases.exists():
            # اگر هیچ خریدی وجود ندارد، فایل خالی برگردان
            wb = Workbook()
            ws = wb.active
            ws.title = 'خریدهای خارج از بازارگاه'
            ws.cell(row=1, column=1, value='هیچ خریدی یافت نشد')
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=non_bazargah_purchases_empty_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb.save(response)
            return response
        
        # ایجاد DataFrame
        data = []
        for purchase in purchases:
            purchase_data = get_purchase_data(purchase, visible_columns)
            data.append(purchase_data)
        
        if not data:
            # اگر داده‌ای وجود ندارد، فایل خالی برگردان
            wb = Workbook()
            ws = wb.active
            ws.title = 'خریدهای خارج از بازارگاه'
            ws.cell(row=1, column=1, value='هیچ داده‌ای برای نمایش وجود ندارد')
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=non_bazargah_purchases_empty_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb.save(response)
            return response
        
        df = pd.DataFrame(data)
        
        # ایجاد HTTP response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=non_bazargah_purchases_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        # ایجاد workbook و worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = 'خریدهای خارج از بازارگاه'
        
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
        logger.error(f"خطا در خروجی اکسل خریدهای خارج از بازارگاه: {str(e)}")
        
        # در صورت خطا، فایل اکسل با پیام خطا برگردان
        wb = Workbook()
        ws = wb.active
        ws.title = 'خطا'
        ws.cell(row=1, column=1, value=f'خطا در ایجاد فایل اکسل: {str(e)}')
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response
