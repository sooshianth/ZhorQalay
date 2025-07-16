from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from openpyxl import Workbook
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
import json
from django.utils import timezone
import logging
import traceback

from core.CargoProductModel import CargoProduct
from django.core.exceptions import ValidationError
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from datetime import datetime
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from core.PurchaseModel import Purchase, PurchaseEditLog
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .managers_profile_view import get_client_ip

logger = logging.getLogger("erp_purchase_list_view")

def get_allowed_columns(user_role):
    allowed_columns = []
    if user_role == 'sales_agent':
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight', 'delivered_weight',
         'status', 'cargo', 'product_type', 'customer', 'buyer_name', 'bazaargah_phone_number', 'tahvil_phone_number']
        
    elif user_role == 'support_agent':
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'sales_agent', 'weight',
         'delivered_weight', 'status', 'cargo', 'product_type', 'importer', 'barbary', 'barbary_phone', 'customer',
          'buyer_name']
          
                
    elif user_role == 'financial_manager':
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'sales_agent', 'company_price', 'customer_price', 'weight',
         'delivered_weight', 'first_barnameh_date', 'last_barnameh_date', 'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'status', 'description', 'is_fully_tasvied',
         'ready_for_invoice', 'is_factored', 'purchase_mabna_invoice', 'sales_mabna_invoice',
          'cargo', 'product_type', 'importer', 'buyer_name', 'code_melli_tahvil', 'address', 'unique_buyer_id']
                
    elif user_role == 'admin' or user_role == 'logistics_manager':
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'sales_agent', 'company_price', 'customer_price', 'weight',
         'delivered_weight', 'first_barnameh_date', 'last_barnameh_date', 'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'status', 'description', 'is_fully_tasvied',
         'ready_for_invoice', 'is_factored', 'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit',
          'cargo', 'product_type', 'importer', 'barbary', 'barbary_phone', 'customer', 'customer_phones', 'buyer_name', 'bazaargah_phone_number', 'tahvil_phone_number', 'code_melli_tahvil', 'address',
            'unique_buyer_id', 'barbary_confidential_number', 'barbary_customer_number', 'delivery_receiver_name', 'buyer_national_id',
            'buyer_user_type', 'unique_delivery_id', 'delivery_address', 'delivery_postal_code', 'vehicle_type', 'factor_status']

    allowed_columns.append('actions')
    return allowed_columns

def get_default_columns(user_role):
    selected_columns = []
    if user_role == 'sales_agent':
        selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight',
             'delivered_weight', 'status', 'cargo', 'product_type', 'customer', 'buyer_name']
    
    elif user_role == 'support_agent':
        selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'sales_agent', 'weight', 
            'delivered_weight', 'status', 'cargo', 'product_type', 'importer' , 'customer', 'buyer_name']
    
    elif user_role == 'financial_manager':
        selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'sales_agent', 'company_price', 'customer_price', 'weight',
             'delivered_weight', 'status', 'description', 'is_fully_tasvied',
             'ready_for_invoice', 'is_factored', 'purchase_mabna_invoice', 'sales_mabna_invoice',
             'cargo', 'product_type', 'importer', 'buyer_name']
    
    elif user_role == 'admin' or user_role == 'logistics_manager':
        selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'sales_agent', 'company_price', 'customer_price', 'weight',
            'delivered_weight', 'status', 'description', 'is_fully_tasvied',
            'ready_for_invoice', 'is_factored', 'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit',
            'cargo', 'product_type', 'importer', 'buyer_name', 'tahvil_phone_number', 'code_melli_tahvil']
          
    return selected_columns

def get_allowed_search_filters(global_search, request):
    user_role = determine_user_role(request.user)
    if user_role == 'sales_agent':
        search_filters = (
                # اطلاعات اصلی خرید
                Q(customer__name__icontains=global_search) |
                Q(purchase_number__icontains=global_search) |
                Q(invoice_id__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                
                # اطلاعات کوتاژ و حمل‌ونقل
                Q(cargo__cottage__icontains=global_search) |
                
                # اطلاعات تماس و آدرس
                Q(address__icontains=global_search) |
                Q(bazaargah_phone_number__icontains=global_search) |
                Q(tahvil_phone_number__icontains=global_search) |
                Q(code_melli_tahvil__icontains=global_search) |
                
                # اطلاعات ردیابی
                Q(unique_buyer_id__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |
                
                # توضیحات و اطلاعات اضافی
                Q(priority_reason__icontains=global_search) |
                
                # نماینده فروش
                Q(unique_sales_agent__name__icontains=global_search)
            )
        search_filters = search_filters & Q(unique_sales_agent__name__icontains=request.user.sales_agent.name)
    elif user_role == 'support_agent':
        search_filters = (
                # اطلاعات اصلی خرید
                Q(customer__name__icontains=global_search) |
                Q(purchase_number__icontains=global_search) |
                Q(invoice_id__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                
                # اطلاعات کوتاژ و حمل‌ونقل
                Q(cargo__cottage__icontains=global_search) |
                Q(cargo__vared_konandeh__name__icontains=global_search) |
                Q(cargo__barbary__name__icontains=global_search) |
                
                # اطلاعات تماس و آدرس
                Q(address__icontains=global_search) |
                Q(bazaargah_phone_number__icontains=global_search) |
                Q(tahvil_phone_number__icontains=global_search) |
                Q(code_melli_tahvil__icontains=global_search) |
                
                # اطلاعات ردیابی
                Q(unique_buyer_id__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |
                
                # توضیحات و اطلاعات اضافی
                Q(priority_reason__icontains=global_search) |
                
                # نماینده فروش
                Q(unique_sales_agent__name__icontains=global_search)
            )
    elif user_role == 'financial_manager':
        search_filters = (
                # اطلاعات اصلی خرید
                Q(customer__name__icontains=global_search) |
                Q(purchase_number__icontains=global_search) |
                Q(invoice_id__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                
                # اطلاعات کوتاژ و حمل‌ونقل
                Q(cargo__cottage__icontains=global_search) |
                Q(cargo__vared_konandeh__name__icontains=global_search) |
                Q(cargo__barbary__name__icontains=global_search) |
                
                # اطلاعات تماس و آدرس
                Q(address__icontains=global_search) |
                Q(bazaargah_phone_number__icontains=global_search) |
                Q(tahvil_phone_number__icontains=global_search) |
                Q(code_melli_tahvil__icontains=global_search) |
                
                # اطلاعات ردیابی
                Q(unique_buyer_id__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |
                
                # توضیحات و اطلاعات اضافی
                Q(description__icontains=global_search) |
                Q(priority_reason__icontains=global_search) |
                
                # نماینده فروش
                Q(unique_sales_agent__name__icontains=global_search)
            )
    elif user_role == 'admin':
        search_filters = (
                # اطلاعات اصلی خرید
                Q(customer__name__icontains=global_search) |
                Q(purchase_number__icontains=global_search) |
                Q(invoice_id__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                
                # اطلاعات کوتاژ و حمل‌ونقل
                Q(cargo__cottage__icontains=global_search) |
                Q(cargo__vared_konandeh__name__icontains=global_search) |
                Q(cargo__barbary__name__icontains=global_search) |
                
                # اطلاعات تماس و آدرس
                Q(address__icontains=global_search) |
                Q(bazaargah_phone_number__icontains=global_search) |
                Q(tahvil_phone_number__icontains=global_search) |
                Q(code_melli_tahvil__icontains=global_search) |
                
                # اطلاعات ردیابی
                Q(unique_buyer_id__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |
                
                # توضیحات و اطلاعات اضافی
                Q(description__icontains=global_search) |
                Q(priority_reason__icontains=global_search) |
                
                # نماینده فروش
                Q(unique_sales_agent__name__icontains=global_search)
            )
    return search_filters

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def purchase_list(request):
    logger.warning(f"لیست خرید توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    # دریافت پارامترهای فیلتر
    global_search = request.GET.get('global_search', '')
    customer = request.GET.get('customer', '')
    sales_agent = request.GET.get('sales_agent', '')
    invoice_id = request.GET.get('invoice_id', '')
    purchase_number = request.GET.get('purchase_number', '')
    cottage = request.GET.get('cottage', '')
    state = request.GET.get('state', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    min_weight = request.GET.get('min_weight', '')
    max_weight = request.GET.get('max_weight', '')
    product_type = request.GET.get('product_type', '')
    country = request.GET.get('country', '')
    is_archived = request.GET.get('is_archived', '')
    is_factored = request.GET.get('is_factored', '')
    priority = request.GET.get('priority', '')
    
    # پارامترهای pagination
    active_page = request.GET.get('active_page', 1)
    pending_page = request.GET.get('pending_page', 1)
    archived_page = request.GET.get('archived_page', 1)
    per_page_param = request.GET.get('per_page', 100)
    
    # بررسی گزینه "نمایش همه"
    if per_page_param == 'all':
        per_page = 10000  # عدد بزرگ برای نمایش همه
    else:
        per_page = int(per_page_param)  # تغییر پیش‌فرض به 100
    
    # پارامترهای فیلتر اضافی
    factor_code = request.GET.get('factor_code', '')
    is_urgent = request.GET.get('is_urgent', '')
    is_canceled = request.GET.get('is_canceled', '')
    is_fully_tasvied = request.GET.get('is_fully_tasvied', '')
    type = request.GET.get('type', '')
    payment_method = request.GET.get('payment_method', '')
    extelaf_type = request.GET.get('extelaf_type', '')
    send_cottage_sms = request.GET.get('send_cottage_sms', '')
    
    # بررسی اینکه آیا درخواست AJAX است
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # تشخیص محدودیت‌های نمایش بر اساس نقش کاربر
    hide_sensitive_info = user_role in ['sales_agent', 'support_agent']
    
    # فیلتر پایه: تقسیم‌بندی خریدها به سه دسته
    # فقط فیلدهای ضروری را انتخاب می‌کنیم
    selected_fields = [
        'id', 'created_at', 'updated_at', 'purchase_number', 'invoice_id', 
        'order_weight', 'delivered_weight', 'state', 'is_factored', 'is_urgent', 
        'is_canceled', 'is_archived', 'company_price', 'customer_price', 
        'amount_paid', 'factor_code', 'unique_sales_agent', 'ready_for_invoice',
        'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit',
        'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'description',
        'is_fully_tasvied', 'buyer_name', 'bazaargah_phone_number', 
        'tahvil_phone_number', 'code_melli_tahvil', 'address'
    ]
    
    # فیلدهای customer و cargo
    customer_fields = ['customer__id', 'customer__name']
    cargo_fields = ['cargo__id', 'cargo__cottage', 'cargo__product_type', 'cargo__barbary__name', 'cargo__barbary__phone_number', 'cargo__vared_konandeh__name']
    
    all_fields = selected_fields + customer_fields + cargo_fields
    
    # ایجاد QuerySet پایه
    base_queryset = Purchase.objects.only(*all_fields)\
        .select_related('customer', 'cargo', 'unique_sales_agent', 'cargo__barbary', 'cargo__vared_konandeh')\
        .prefetch_related('customer__phone_numbers', 'barnamehs')\
        .order_by('-created_at')
    
    # تقسیم‌بندی خریدها به سه دسته:
    # 1. خریدهای فعال (به جز آرشیو و در انتظار پرداخت)
    active_purchases = base_queryset.exclude(state='ARCHIVED')\
        .exclude(is_archived=True)\
        .exclude(state__in=['SMS_SENT', 'INITIATED'])
        
    # 2. خریدهای در انتظار پرداخت (SMS_SENT و INITIATED)
    pending_payment_purchases = base_queryset.filter(state__in=['SMS_SENT', 'INITIATED'])\
        .exclude(is_archived=True)
        
    # 3. خریدهای آرشیو شده
    archived_purchases = base_queryset.filter(Q(state='ARCHIVED') | Q(is_archived=True))

    # اگر کاربر کارشناس فروش یا پیگیری است، فقط خریدهای مربوطه را ببیند
    if user_role == 'sales_agent':
        # بررسی اینکه آیا کاربر sales_agent دارد یا نه
        if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
            # فیلتر مستقیم بر اساس unique_sales_agent
            sales_agent_filter = Q(unique_sales_agent=request.user.sales_agent)
            active_purchases = active_purchases.filter(sales_agent_filter)
            pending_payment_purchases = pending_payment_purchases.filter(sales_agent_filter)
            archived_purchases = archived_purchases.filter(sales_agent_filter)
        else:
            # اگر کاربر sales_agent ندارد، هیچ خریدی نمایش نده
            active_purchases = Purchase.objects.none()
            pending_payment_purchases = Purchase.objects.none()
            archived_purchases = Purchase.objects.none()
    elif user_role == 'support_agent':
        # کارشناس پیگیری همه خریدها را می‌بیند اما با محدودیت اطلاعات
        pass

    # اگر فیلتر وضعیت آرشیو انتخاب شده است
    if is_archived != '':
        if is_archived == '1':
            # نمایش فقط آرشیو - active را خالی می‌کنیم
            active_purchases = Purchase.objects.none()
            pending_payment_purchases = Purchase.objects.none()
        else:  # is_archived == '0'
            # نمایش فقط فعال - آرشیو را خالی می‌کنیم
            archived_purchases = Purchase.objects.none()

    # اعمال فیلترهای پیشرفته (بهینه شده)
    filters = Q()
    
    if customer:
        filters &= Q(customer__name__icontains=customer)
    
    if sales_agent:
        # جستجو مستقیم در کارشناس فروش
        filters &= Q(unique_sales_agent__name__icontains=sales_agent)
    
    if invoice_id:
        filters &= Q(invoice_id__icontains=invoice_id)
    
    if purchase_number:
        filters &= Q(purchase_number__icontains=purchase_number)
    
    if cottage:
        filters &= Q(cargo__cottage__icontains=cottage)
    
    if state:
        filters &= Q(state=state)
    
    # فیلتر تاریخ
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            filters &= Q(created_at__date__gte=date_from_obj)
        except ValueError:
            pass  # تاریخ نامعتبر نادیده گرفته می‌شود
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            filters &= Q(created_at__date__lte=date_to_obj)
        except ValueError:
            pass  # تاریخ نامعتبر نادیده گرفته می‌شود
    
    # فیلترهای اضافی (ساده شده)
    if is_factored != '':
        filters &= Q(is_factored=(is_factored == '1'))
    
    if is_urgent == '1':
        filters &= Q(is_urgent=True)
    
    # اعمال فیلتر جستجوی سریع - جستجو در همه فیلدهای مهم
    if global_search:
        search_filters = (
            # اطلاعات اصلی خرید
            Q(customer__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(buyer_name__icontains=global_search) |
            
            # اطلاعات کوتاژ و حمل‌ونقل
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__vared_konandeh__name__icontains=global_search) |
            Q(cargo__barbary__name__icontains=global_search) |
            
            # اطلاعات تماس و آدرس
            Q(address__icontains=global_search) |
            Q(bazaargah_phone_number__icontains=global_search) |
            Q(tahvil_phone_number__icontains=global_search) |
            Q(code_melli_tahvil__icontains=global_search) |
            
            # اطلاعات ردیابی
            Q(unique_buyer_id__icontains=global_search) |
            Q(shenase_takhsis_set__code__icontains=global_search) |
            
            # توضیحات و اطلاعات اضافی
            Q(description__icontains=global_search) |
            Q(priority_reason__icontains=global_search) |
            
            # نماینده فروش
            Q(unique_sales_agent__name__icontains=global_search)
        )
        filters &= search_filters
    
    # اعمال همه فیلترها یکجا
    if filters:
        active_purchases = active_purchases.filter(filters)
        pending_payment_purchases = pending_payment_purchases.filter(filters)
        archived_purchases = archived_purchases.filter(filters)
    
    # تنظیم pagination برای هر بخش
    active_paginator = Paginator(active_purchases, per_page)
    pending_paginator = Paginator(pending_payment_purchases, per_page)
    archived_paginator = Paginator(archived_purchases, per_page)
    
    try:
        active_page_obj = active_paginator.page(active_page)
    except (PageNotAnInteger, EmptyPage):
        active_page_obj = active_paginator.page(1)
        active_page = 1
    
    try:
        pending_page_obj = pending_paginator.page(pending_page)
    except (PageNotAnInteger, EmptyPage):
        pending_page_obj = pending_paginator.page(1)
        pending_page = 1
    
    try:
        archived_page_obj = archived_paginator.page(archived_page)
    except (PageNotAnInteger, EmptyPage):
        archived_page_obj = archived_paginator.page(1)
        archived_page = 1
    
    # فهرست وضعیت‌ها برای فیلتر
    all_states = dict(Purchase.STATUS_CHOICES)

    if user_role == 'sales_agent':
        all_columns = [
            {'id': 'actions', 'name': 'جزئیات'},
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            {'id': 'product_type', 'name': 'نام محصول', 'field': 'cargo.product_type'},
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            {'id': 'bazaargah_phone_number', 'name': 'شماره تلفن بازارگاه', 'field': 'bazaargah_phone_number'},
            {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'field': 'tahvil_phone_number'},        
        ]

        # todo: add the rest of the columns
        allowed_columns = get_allowed_columns(user_role)
        
                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = get_default_columns(user_role)
            logger.info("Using default columns for sales agent")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = get_default_columns(user_role)
                logger.error("Type error on selected_columns - using defaults for sales agent")
            
            # فیلتر کردن فقط ستون‌های مجاز
            selected_columns = [col for col in selected_columns if col in allowed_columns]
            if not selected_columns:
                selected_columns = allowed_columns
        
        # اطمینان از حضور ستون actions
        if 'actions' not in selected_columns:
            selected_columns.append('actions')
        
        logger.warning(f"ستون های انتخابی مسئول فروش {request.user.username}: {selected_columns}")
        logger.info(f"ستون های قابل انتخاب مسئول فروش {request.user.username}: {all_columns}")

    elif user_role == 'support_agent':
        all_columns = [
            {'id': 'actions', 'name': 'جزئیات'},
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            {'id': 'sales_agent', 'name': 'نماینده فروش', 'field': 'customer.sales_agent.name'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            {'id': 'product_type', 'name': 'نام محصول', 'field': 'cargo.product_type'},
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'barbary', 'name': 'نام باربری', 'field': 'cargo.barbary.name'},
            {'id': 'barbary_phone', 'name': 'شماره باربری', 'field': 'cargo.barbary.phone_number'},
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},

        ]

        # todo: add the rest of the columns
        allowed_columns = get_allowed_columns(user_role)
                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = get_default_columns(user_role)
            logger.info("Using default columns for support agent")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = get_default_columns(user_role)
                logger.error("Type error on selected_columns - using defaults for support agent")
            
            # فیلتر کردن فقط ستون‌های مجاز
            selected_columns = [col for col in selected_columns if col in allowed_columns]
            if not selected_columns:
                selected_columns = allowed_columns
        
        # اطمینان از حضور ستون actions
        if 'actions' not in selected_columns:
            selected_columns.append('actions')
        
        logger.warning(f"ستون های انتخابی مسئول پیگیری {request.user.username}: {selected_columns}")
        logger.info(f"ستون های قابل انتخاب مسئول پیگیری {request.user.username}: {all_columns}")
    elif user_role == 'financial_manager':
        all_columns = [
            {'id': 'actions', 'name': 'جزئیات'},
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            {'id': 'sales_agent', 'name': 'نماینده فروش', 'field': 'customer.sales_agent.name'},
            {'id': 'company_price', 'name': 'فی خرید', 'field': 'company_price', 'unit': 'ریال'},
            {'id': 'customer_price', 'name': 'فی فروش', 'field': 'customer_price', 'unit': 'ریال'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'first_barnameh_date', 'name': 'تاریخ اولین بارنامه', 'field': 'barnamehs.first.barnameh_date', 'format': 'date'},
            {'id': 'last_barnameh_date', 'name': 'تاریخ آخرین بارنامه', 'field': 'barnamehs.last.barnameh_date', 'format': 'date'},
            {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'field': 'extelaf_type'},
            {'id': 'extelaf_weight', 'name': 'وزن اختلاف', 'field': 'extelaf_weight', 'unit': 'کیلوگرم'},
            {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف', 'field': 'extelaf_amount', 'unit': 'ریال'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'description', 'name': 'توضیحات', 'field': 'description'},
            {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'field': 'is_fully_tasvied'},
            {'id': 'ready_for_invoice', 'name': 'آماده فاکتور', 'field': 'ready_for_invoice'},
            {'id': 'is_factored', 'name': 'صدور فاکتور', 'field': 'is_factored'},
            {'id': 'purchase_mabna_invoice', 'name': 'فاکتور خرید مبنا', 'field': 'purchase_mabna_invoice', 'unit': 'ریال'},
            {'id': 'sales_mabna_invoice', 'name': 'فاکتور فروش مبنا', 'field': 'sales_mabna_invoice', 'unit': 'ریال'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            {'id': 'product_type', 'name': 'نام محصول', 'field': 'cargo.product_type'},
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            {'id': 'code_melli_tahvil', 'name': 'کد ملی تحویل', 'field': 'code_melli_tahvil'},
            {'id': 'address', 'name': 'آدرس خریدار', 'field': 'address'},
            {'id': 'unique_buyer_id', 'name': 'شناسه یکتا خریدار', 'field': 'unique_buyer_id'},
            {'id': 'factor_status', 'name': 'وضعیت فاکتور', 'field': 'factor_status'},
        ]

        # todo: add the rest of the columns
        allowed_columns = get_allowed_columns(user_role)
                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = get_default_columns(user_role)
             #  شناسه ملی خریدار، ادرس خریدار، شناسه یکتا خریدار
            logger.info("Using default columns for financial manager")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = get_default_columns(user_role)
                #  شناسه ملی خریدار، ادرس خریدار، شناسه یکتا خریدار
                logger.error("Type error on selected_columns - using defaults for financial manager")
            
            # فیلتر کردن فقط ستون‌های مجاز
            selected_columns = [col for col in selected_columns if col in allowed_columns]
            if not selected_columns:
                selected_columns = allowed_columns
        
        # اطمینان از حضور ستون actions
        if 'actions' not in selected_columns:
            selected_columns.append('actions')
        
        logger.warning(f"ستون های انتخابی مسئول مالی {request.user.username}: {selected_columns}")
        logger.info(f"ستون های قابل انتخاب مسئول مالی {request.user.username}: {all_columns}")

    elif user_role == 'admin' or user_role == 'logistics_manager':
        all_columns = [
            {'id': 'actions', 'name': 'جزئیات'},
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            {'id': 'sales_agent', 'name': 'نماینده فروش', 'field': 'customer.sales_agent.name'},
            {'id': 'company_price', 'name': 'فی خرید', 'field': 'company_price', 'unit': 'ریال'},
            {'id': 'customer_price', 'name': 'فی فروش', 'field': 'customer_price', 'unit': 'ریال'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'first_barnameh_date', 'name': 'تاریخ اولین بارنامه', 'field': 'barnamehs.first.barnameh_date', 'format': 'date'},
            {'id': 'last_barnameh_date', 'name': 'تاریخ آخرین بارنامه', 'field': 'barnamehs.last.barnameh_date', 'format': 'date'},
            {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'field': 'extelaf_type'},
            {'id': 'extelaf_weight', 'name': 'وزن اختلاف', 'field': 'extelaf_weight', 'unit': 'کیلوگرم'},
            {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف', 'field': 'extelaf_amount', 'unit': 'ریال'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'description', 'name': 'توضیحات', 'field': 'description'},
            {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'field': 'is_fully_tasvied'},
            {'id': 'ready_for_invoice', 'name': 'آماده فاکتور', 'field': 'ready_for_invoice'},
            {'id': 'is_factored', 'name': 'صدور فاکتور', 'field': 'is_factored'},
            {'id': 'purchase_mabna_invoice', 'name': 'فاکتور خرید مبنا', 'field': 'purchase_mabna_invoice', 'unit': 'ریال'},
            {'id': 'sales_mabna_invoice', 'name': 'فاکتور فروش مبنا', 'field': 'sales_mabna_invoice', 'unit': 'ریال'},
            {'id': 'mabna_profit', 'name': 'سود مبنا', 'field': 'mabna_profit', 'unit': 'ریال'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            {'id': 'product_type', 'name': 'نام محصول', 'field': 'cargo.product_type'},
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'barbary', 'name': 'نام باربری', 'field': 'cargo.barbary.name'},
            {'id': 'barbary_phone', 'name': 'شماره باربری', 'field': 'cargo.barbary.phone_number'},
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
             {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            {'id': 'bazaargah_phone_number', 'name': 'شماره تلفن بازارگاه', 'field': 'bazaargah_phone_number'},
            {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'field': 'tahvil_phone_number'},
            {'id': 'code_melli_tahvil', 'name': 'کد ملی تحویل', 'field': 'code_melli_tahvil'},
            {'id': 'address', 'name': 'آدرس خریدار', 'field': 'address'},
            {'id': 'unique_buyer_id', 'name': 'شناسه یکتا خریدار', 'field': 'unique_buyer_id'},
            {'id': 'barbary_confidential_number', 'name': 'شماره باربری محرمانه', 'field': 'barbary_confidential_number'},
            {'id': 'barbary_customer_number', 'name':'شماره باربری مشتری', 'field': 'barbary_customer_number'},
            {'id': 'delivery_receiver_name', 'name':'نام تحویل گیرنده', 'field': 'delivery_receiver_name'},
            {'id': 'buyer_national_id', 'name':'شناسه ملی خریدار', 'field': 'buyer_national_id'},
            {'id': 'buyer_user_type', 'name':'نوع کاربری خریدار', 'field': 'buyer_user_type'},
            {'id': 'unique_delivery_id', 'name':'شناسه یکتا تحویل', 'field': 'unique_delivery_id'},
            {'id': 'delivery_address', 'name':'آدرس تحویل', 'field': 'delivery_address'},
            {'id': 'delivery_postal_code', 'name':'کد پستی تحویل', 'field': 'delivery_postal_code'},
            {'id': 'vehicle_type', 'name':'نوع خودرو حمل', 'field': 'vehicle_type'},
            {'id': 'factor_status', 'name': 'وضعیت فاکتور', 'field': 'factor_status'},
        ]

        # todo: add the rest of the columns
        allowed_columns = get_allowed_columns(user_role)

                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = get_default_columns(user_role)
            logger.info("Using default columns for admin")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = get_default_columns(user_role)
                logger.error("Type error on selected_columns - using defaults for admin")
            
            # فیلتر کردن فقط ستون‌های مجاز
            selected_columns = [col for col in selected_columns if col in allowed_columns]
            if not selected_columns:
                selected_columns = allowed_columns
        
        # اطمینان از حضور ستون actions
        if 'actions' not in selected_columns:
            selected_columns.append('actions')
        
        logger.warning(f"ستون های انتخابی ادمین {request.user.username}: {selected_columns}")
        logger.info(f"ستون های قابل انتخاب ادمین {request.user.username}: {all_columns}")
    """if user_role == 'admin':
        # دریافت ستون های انتخاب شده از کوکی برای کاربران غیرمحدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        # For debugging
        print(f"Cookie selected_columns for unrestricted user: '{selected_columns}'")
        
        if not selected_columns:
            selected_columns = 'purchase_number,date,customer,invoice_id,sales_agent,weight,cargo,status,actions'
            print("Using default columns for unrestricted user")
        
        # Make sure we have a string before splitting
        if isinstance(selected_columns, str):
            selected_columns = selected_columns.split(',')
        else:
            selected_columns = ['purchase_number', 'date', 'customer', 'invoice_id', 'sales_agent', 'weight', 'cargo', 'status', 'actions']
            print("Type error on selected_columns - using defaults for unrestricted user")
        
        # اطمینان از حضور ستون actions
        if 'actions' not in selected_columns:
            selected_columns.append('actions')
        
        print(f"Final selected columns for unrestricted user: {selected_columns}")
        
        # لیست همه ستون های ممکن با اطلاعات لازم برای سایر نقش‌ها
        all_columns = [
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
            {'id': 'invoice_id', 'name': 'کد درون سازمانی', 'field': 'invoice_id'},
            {'id': 'sales_agent', 'name': 'نماینده فروش', 'field': 'customer.sales_agent.name'},
            {'id': 'weight', 'name': 'وزن', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'status', 'name': 'وضعیت‌ها', 'field': 'state'},
            {'id': 'actions', 'name': 'جزئیات'},
            # ستون‌های اضافی
            {'id': 'address', 'name': 'آدرس', 'field': 'address'},
            {'id': 'description', 'name': 'توضیحات', 'field': 'description'},
            {'id': 'factor_code', 'name': 'فاکتور مبنا', 'field': 'factor_code'},
            {'id': 'tracking_number', 'name': 'شماره پیگیری', 'field': 'tracking_number'},
            {'id': 'shenase_takhsis', 'name': 'شناسه‌های تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'code_melli_tahvil', 'name': 'کد ملی تحویل', 'field': 'code_melli_tahvil'},
            {'id': 'bazaargah_phone_number', 'name': 'شماره تلفن بازارگاه', 'field': 'bazaargah_phone_number'},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'field': 'tahvil_phone_number'},
            {'id': 'send_cottage_sms', 'name': 'ارسال پیامک کوتاژ', 'field': 'send_cottage_sms'},
            {'id': 'total_weight', 'name': 'وزن کل', 'field': 'total_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'type', 'name': 'نوع خرید', 'field': 'type'},
            {'id': 'payment_method', 'name': 'شیوه پرداخت', 'field': 'payment_method'},
            {'id': 'updated_at', 'name': 'تاریخ بروزرسانی', 'field': 'updated_at'},
            {'id': 'is_weight_costed', 'name': 'کسر از وزن موجود', 'field': 'is_weight_costed'},
            {'id': 'is_ap_af', 'name': 'اتوکامپلیت شده', 'field': 'is_ap_af'},
            {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'field': 'extelaf_type'},
            {'id': 'extelaf_weight', 'name': 'وزن اختلاف', 'field': 'extelaf_weight', 'unit': 'کیلوگرم'},
            {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف', 'field': 'extelaf_amount', 'unit': 'ریال'},
            {'id': 'is_urgent', 'name': 'فوری', 'field': 'is_urgent'},
            {'id': 'is_canceled', 'name': 'لغو شده', 'field': 'is_canceled'},
            {'id': 'is_archived', 'name': 'آرشیو شده', 'field': 'is_archived'},
            {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'field': 'is_fully_tasvied'},
            {'id': 'is_factored', 'name': 'ثبت فاکتور', 'field': 'is_factored'},
            {'id': 'priority', 'name': 'اولویت', 'field': 'priority'},
            {'id': 'priority_reason', 'name': 'دلیل اولویت', 'field': 'priority_reason'},
            {'id': 'barbary', 'name': 'نام باربری', 'field': 'cargo.barbary.name'},
            {'id': 'customer_price', 'name': 'فی فروش', 'field': 'customer_price', 'unit': 'ریال'},
        ]
        
        # اضافه کردن ستون‌های حساس فقط برای نقش‌های مجاز
        if not hide_sensitive_info:
            all_columns.extend([
                {'id': 'company_price', 'name': 'فی خرید', 'field': 'company_price', 'unit': 'ریال'},
                {'id': 'amount_paid', 'name': 'مبلغ پرداختی', 'field': 'amount_paid', 'unit': 'ریال'},
            ])
        logger.warning(f"ستون های انتخابی کاربر نامحدود {request.user.username}: {selected_columns}")
        logger.warning(f"ستون های قابل انتخاب کاربر نامحدود {request.user.username}: {all_columns}")"""

    # اگر درخواست AJAX است، فقط داده‌های JSON برگردان
    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'data': {
                'active': {
                    'has_previous': active_page_obj.has_previous(),
                    'has_next': active_page_obj.has_next(),
                    'number': active_page_obj.number,
                    'num_pages': active_paginator.num_pages,
                    'count': active_paginator.count,
                    'page_range': list(active_paginator.get_elided_page_range(active_page_obj.number, on_each_side=2, on_ends=1)),
                },
                'pending': {
                    'has_previous': pending_page_obj.has_previous(),
                    'has_next': pending_page_obj.has_next(),
                    'number': pending_page_obj.number,
                    'num_pages': pending_paginator.num_pages,
                    'count': pending_paginator.count,
                    'page_range': list(pending_paginator.get_elided_page_range(pending_page_obj.number, on_each_side=2, on_ends=1)),
                },
                'archived': {
                    'has_previous': archived_page_obj.has_previous(),
                    'has_next': archived_page_obj.has_next(),
                    'number': archived_page_obj.number,
                    'num_pages': archived_paginator.num_pages,
                    'count': archived_paginator.count,
                    'page_range': list(archived_paginator.get_elided_page_range(archived_page_obj.number, on_each_side=2, on_ends=1)),
                }
            }
        })

    context = {
        'active_purchases': active_page_obj,
        'pending_payment_purchases': pending_page_obj,
        'archived_purchases': archived_page_obj,
        'pending_payment_count': pending_paginator.count,
        'archived_count': archived_paginator.count,
        'all_states': all_states,
        'user_role': user_role,
        'hide_sensitive_info': hide_sensitive_info,
        'is_restricted_user': user_role in ['sales_agent', 'support_agent'],  # برای غیرفعال کردن drag & drop
        'total_active_purchases': active_paginator.count,  # تعداد واقعی رکوردها
        'search_params': {
            'global_search': global_search,
            'customer': customer,
            'sales_agent': sales_agent,
            'invoice_id': invoice_id,
            'purchase_number': purchase_number,
            'cottage': cottage,
            'state': state,
            'is_archived': is_archived,
            'per_page': per_page_param,  # ارسال مقدار اصلی، نه عدد تبدیل شده
        },
        'selected_columns': selected_columns,
        'all_columns': all_columns,
        # اضافه کردن pagination info
        'pagination': {
            'active': {
                'paginator': active_paginator,
                'page_obj': active_page_obj,
                'current_page': int(active_page),
            },
            'pending': {
                'paginator': pending_paginator,
                'page_obj': pending_page_obj,
                'current_page': int(pending_page),
            },
            'archived': {
                'paginator': archived_paginator,
                'page_obj': archived_page_obj,
                'current_page': int(archived_page),
            }
        }
    }
    
    return render(request, 'purchase_list.html', context)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def load_archived_purchases(request):
    """
    API برای بارگذاری lazy خریدهای آرشیو شده
    """
    logger.warning(f"هشدار! خرید های ارشیو شده توسط {request.user.username} لود شد. {get_client_ip(request)}")
    return JsonResponse({
            'status': 'success',
            'data': [],
            'count': 0
        })
    
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        # فیلدهای ضروری برای آرشیو
        archived_fields = [
            'id', 'created_at', 'purchase_number', 'invoice_id', 
            'order_weight', 'state', 'is_factored', 'customer__name', 'cargo__cottage'
        ]
        
        # دریافت خریدهای آرشیو شده
        archived_purchases = Purchase.objects.filter(
            Q(state='ARCHIVED') | Q(is_archived=True)
        ).only(*archived_fields).select_related('customer', 'cargo').order_by('-created_at')[:200]
        
        # فیلتر برای کارشناس فروش
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                archived_purchases = archived_purchases.filter(unique_sales_agent=request.user.sales_agent)
            else:
                # اگر کاربر sales_agent ندارد، هیچ خریدی نمایش نده
                archived_purchases = Purchase.objects.none()
        
        # تبدیل به JSON
        data = []
        for purchase in archived_purchases:
            data.append({
                'id': purchase.id,
                'purchase_number': purchase.purchase_number or 'تعیین نشده',
                'customer_name': purchase.customer.name if purchase.customer else '-',
                'invoice_id': purchase.invoice_id or 'تعیین نشده',
                'order_weight': f"{purchase.order_weight:,}" if purchase.order_weight else '0',
                'cottage': purchase.cargo.cottage if purchase.cargo else '-',
                'state': purchase.get_state_display(),
                'created_at': purchase.created_at.strftime("%Y/%m/%d") if purchase.created_at else '-',
            })
        
        return JsonResponse({
            'status': 'success',
            'data': data,
            'count': len(data)
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
@login_required
def update_columns(request):
    """
    به‌روزرسانی ستون‌های انتخاب شده برای نمایش در لیست خریدها
    """
    logger.warning(f"ستون های لیست خرید اپدیت شدند توسط {request.user.username} و {get_client_ip(request)}")
    try:
        # دریافت ستون‌های انتخاب شده از فرم
        selected_columns = request.POST.getlist('columns[]')

        # بررسی فرمت‌های مختلف داده
        if not selected_columns and 'columns' in request.POST:
            selected_columns = request.POST.getlist('columns')


        # اگر هنوز ستونی یافت نشد، تلاش برای فرمت رشته‌ای
        if not selected_columns and request.POST.get('columns'):
            columns_str = request.POST.get('columns')
            selected_columns = [c.strip() for c in columns_str.split(',') if c.strip()]

        # بررسی وجود ستون‌های انتخاب شده
        if not selected_columns:
            return JsonResponse({
                'status': 'error', 
                'message': 'هیچ ستونی انتخاب نشده است'
            }, status=400)
        
        logger.warning(f"ستون‌های دریافت شده: {selected_columns} برای {request.user.username}")

        # فیلتر کردن ستون‌های انتخاب شده برای کاربران محدود
        user_role = determine_user_role(request.user)
        allowed_columns = get_allowed_columns(user_role)

        selected_columns = [col for col in selected_columns if col in allowed_columns]
        if not selected_columns:
            selected_columns = allowed_columns

        # اطمینان از وجود ستون عملیات
        if 'actions' not in selected_columns:
            selected_columns.append('actions')  # ستون جزئیات همیشه باید نمایش داده شود
        
        # ایجاد پاسخ و تنظیم کوکی
        cookie_value = ','.join(selected_columns)

        response = JsonResponse({'status': 'success', 'selected_columns': selected_columns})
        
        # تنظیم کوکی با عمر 30 روز
        response.set_cookie(
            'selected_columns', 
            cookie_value, 
            max_age=30*24*60*60,  # 30 روز
            httponly=False,       # اجازه دسترسی از JavaScript
            samesite='Lax'        # اجازه ارسال در navigations
        )
        
        return response
    except Exception as e:
        import traceback
        logger.error(f"خطا در update_columns: {str(e)}, {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': "خطا در اپدیت ستون های لیست خرید"}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def export_to_excel(request):
    logger.warning(f"خروجی اکسل توسط {request.user.username} با متد {request.method} و آی‌پی {get_client_ip(request)} آغاز شد")
    # Support both GET and POST requests
    if request.method == 'POST':
        purchase_ids = request.POST.get('ids', '').split(',')
        selected_columns = request.POST.get('columns', '')
    else:
        purchase_ids = request.GET.get('ids', '').split(',')
        selected_columns = request.GET.get('columns', '')
    logger.warning(f"raw select columns for user {request.user.username}: {selected_columns}")

    user_role = determine_user_role(request.user)
    allowed_columns = get_allowed_columns(user_role)

    if selected_columns:
        # حذف کوتیشن‌های اضافی و decode کردن کاراکترهای escape شده
        selected_columns = selected_columns.strip('"').replace('\\054', ',').replace('\\\\', '\\')
        selected_columns = selected_columns.split(',')
        # حذف actions از لیست ستون‌ها چون در اکسل نمی‌خواهیم
        selected_columns = [col.strip() for col in selected_columns if col.strip() and col.strip() != 'actions']

        selected_columns = [col for col in selected_columns if col in allowed_columns]
        if not selected_columns:
            selected_columns = allowed_columns
    else:
        selected_columns = get_default_columns(user_role)
    
    
    # فیلتر کردن آیدی‌های خالی
    purchase_ids = [pid.strip() for pid in purchase_ids if pid.strip()]

    if not purchase_ids:
        logger.warning("ERROR: No purchase IDs to export excel!")
        return JsonResponse({'status': 'error', 'message': 'هیچ خریدی انتخاب نشده است'}, status=400)
    
    # بررسی تعداد خریدها
    total_count = len(purchase_ids)
    logger.warning(f"Total purchases to export: {total_count}")
    
    try:
        # استفاده از روش معمولی برای همه خریدها
        return _export_regular_excel(purchase_ids, selected_columns)
            
    except Exception as e:
        # لاگ خطا
        import traceback
        logger.warning(f"Error in export_to_excel: {str(e)}, {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد فایل اکسل:'}, status=500)

def _export_regular_excel(purchase_ids, selected_columns):
    """پردازش معمولی برای تعداد کم خرید"""
    purchases = Purchase.objects.filter(id__in=purchase_ids).select_related(
        'customer', 'cargo', 'unique_sales_agent'
    ).prefetch_related(
        'shenase_takhsis_set', 'cargo__barbary', 'cargo__vared_konandeh', 'customer__sales_agent'
    ).order_by('-created_at')
    
    logger.warning(f"Found {purchases.count()} purchases")
    
    if purchases.count() == 0:
        logger.warning("ERROR: No purchases found!")
        return JsonResponse({'status': 'error', 'message': 'هیچ خریدی با شناسه‌های داده شده یافت نشد'}, status=400)
    
    wb = Workbook()
    ws = wb.active
    ws.title = "لیست خریدها"
    
    # مپینگ کامل ستون‌ها به فیلدهای مدل - پشتیبانی از همه فیلدها
    column_mapping = {
        'purchase_number': ('شماره خرید', lambda p: p.purchase_number or "تعیین نشده"),
        'shenase_takhsis': ('شناسه‌های تخصیص', lambda p: ", ".join([st.code for st in p.shenase_takhsis_set.all()]) if hasattr(p, 'shenase_takhsis_set') and p.shenase_takhsis_set.exists() else "-"),
        'date': ('تاریخ', lambda p: p.created_at.strftime("%Y/%m/%d") if p.created_at else "-"),
        'sales_agent': ('نماینده فروش', lambda p: p.unique_sales_agent.name if p.unique_sales_agent else (", ".join([agent.name for agent in p.customer.sales_agent.all()]) if p.customer and p.customer.sales_agent.exists() else "-")),
        'customer': ('نام مشتری', lambda p: p.customer.name if p.customer else "نامشخص"),
        'invoice_id': ('کد درون سازمانی', lambda p: p.invoice_id or "تعیین نشده"),
        'weight': ('وزن (کیلوگرم)', lambda p: f"{p.order_weight:,}" if p.order_weight else "0"),
        'cargo': ('کوتاژ', lambda p: p.cargo.cottage if p.cargo and hasattr(p.cargo, 'cottage') else "-"),
        'importer': ('واردکننده', lambda p: p.cargo.vared_konandeh.name if p.cargo and hasattr(p.cargo, 'vared_konandeh') and p.cargo.vared_konandeh else "-"),
        'status': ('وضعیت', lambda p: dict(Purchase.STATUS_CHOICES).get(p.state, p.state) if p.state else "-"),
        'address': ('آدرس', lambda p: p.address or "-"),
        'description': ('توضیحات', lambda p: p.description or "-"),
        'factor_code': ('فاکتور مبنا', lambda p: "بله" if p.factor_code else "خیر"),
        'unique_buyer_id': ('شناسه یکتا خریدار', lambda p: p.unique_buyer_id or "-"),
        'factor_status': ('وضعیت فاکتور', lambda p: p.factor_status or "-"),
        'code_melli_tahvil': ('کد ملی تحویل', lambda p: p.code_melli_tahvil or "-"),
        'bazaargah_phone_number': ('شماره تلفن بازارگاه', lambda p: p.bazaargah_phone_number or "-"),
        'buyer_name': ('نام خریدار', lambda p: p.buyer_name or "-"),
        'tahvil_phone_number': ('شماره تلفن تحویل', lambda p: p.tahvil_phone_number or "-"),
        'send_cottage_sms': ('ارسال پیامک کوتاژ', lambda p: "بله" if p.send_cottage_sms else "خیر"),
        'total_weight': ('وزن کل (کیلوگرم)', lambda p: f"{p.total_weight:,}" if p.total_weight else "0"),
        'delivered_weight': ('وزن بارنامه شده (کیلوگرم)', lambda p: f"{p.delivered_weight:,}" if p.delivered_weight else "0"),
        'type': ('نوع خرید', lambda p: "بازارگاه" if p.type == "bazaargah" else "خارج از بازارگاه" if p.type == "non_bazaargah" else p.type or "-"),
        'payment_method': ('شیوه پرداخت', lambda p: p.payment_method or "-"),
        'updated_at': ('تاریخ بروزرسانی', lambda p: p.updated_at.strftime("%Y/%m/%d") if p.updated_at else "-"),
        'is_weight_costed': ('کسر از وزن موجود', lambda p: "بله" if p.is_weight_costed else "خیر"),
        'is_ap_af': ('اتوکامپلیت شده', lambda p: "بله" if p.is_ap_af else "خیر"),
        'extelaf_type': ('نوع اختلاف', lambda p: p.extelaf_type or "-"),
        'extelaf_weight': ('وزن اختلاف (کیلوگرم)', lambda p: f"{p.extelaf_weight:,}" if p.extelaf_weight else "0"),
        'extelaf_amount': ('مبلغ اختلاف (ریال)', lambda p: f"{p.extelaf_amount:,}" if p.extelaf_amount else "0"),
        'is_urgent': ('فوری', lambda p: "بله" if p.is_urgent else "خیر"),
        'is_canceled': ('لغو شده', lambda p: "بله" if p.is_canceled else "خیر"),
        'is_archived': ('آرشیو شده', lambda p: "بله" if p.is_archived else "خیر"),
        'is_fully_tasvied': ('تسویه کامل', lambda p: "بله" if p.is_fully_tasvied else "خیر"),
        'is_factored': ('ثبت فاکتور', lambda p: "بله" if p.is_factored else "خیر"),
        'ready_for_invoice': ('آماده فاکتور', lambda p: "بله" if p.ready_for_invoice else "خیر"),
        'purchase_mabna_invoice': ('فاکتور خرید مبنا (ریال)', lambda p: f"{p.purchase_mabna_invoice:,}" if p.purchase_mabna_invoice else "0"),
        'sales_mabna_invoice': ('فاکتور فروش مبنا (ریال)', lambda p: f"{p.sales_mabna_invoice:,}" if p.sales_mabna_invoice else "0"),
        'mabna_profit': ('سود مبنا (ریال)', lambda p: f"{p.mabna_profit:,}" if p.mabna_profit else "0"),
        'priority': ('اولویت', lambda p: dict(Purchase.PRIORITY_CHOICES).get(p.priority, p.priority) if p.priority else "-"),
        'priority_reason': ('دلیل اولویت', lambda p: p.priority_reason or "-"),
        'barbary': ('نام باربری', lambda p: p.cargo.barbary.name if p.cargo and hasattr(p.cargo, 'barbary') and p.cargo.barbary else "-"),
        'barbary_phone': ('شماره باربری', lambda p: p.cargo.barbary.phone_number if p.cargo and hasattr(p.cargo, 'barbary') and p.cargo.barbary and p.cargo.barbary.phone_number else "-"),
        'product_type': ('نام محصول', lambda p: p.cargo.get_product_type_display() if p.cargo and hasattr(p.cargo, 'product_type') and p.cargo.product_type else "-"),
        'first_barnameh_date': ('تاریخ اولین بارنامه', lambda p: p.barnamehs.order_by('barnameh_date').first().barnameh_date.strftime("%Y/%m/%d") if hasattr(p, 'barnamehs') and p.barnamehs.exists() and p.barnamehs.order_by('barnameh_date').first().barnameh_date else "-"),
        'last_barnameh_date': ('تاریخ آخرین بارنامه', lambda p: p.barnamehs.order_by('-barnameh_date').first().barnameh_date.strftime("%Y/%m/%d") if hasattr(p, 'barnamehs') and p.barnamehs.exists() and p.barnamehs.order_by('-barnameh_date').first().barnameh_date else "-"),
        'company_price': ('فی خرید (ریال)', lambda p: f"{p.company_price:,}" if p.company_price else "0"),
        'customer_price': ('فی فروش (ریال)', lambda p: f"{p.customer_price:,}" if p.customer_price else "0"),
        'amount_paid': ('مبلغ پرداختی (ریال)', lambda p: f"{p.amount_paid:,}" if p.amount_paid else "0"),
        'barbary_confidential_number': ('شماره محرمانه باربری', lambda p: p.barbary_confidential_number or "-"),
        'barbary_customer_number': ('شماره مشتری باربری', lambda p: p.barbary_customer_number or "-"),
        'delivery_receiver_name': ('نام تحویل گیرنده', lambda p: p.delivery_receiver_name or "-"),
        'buyer_national_id': ('کد ملی خریدار', lambda p: p.buyer_national_id or "-"),
        'buyer_user_type': ('نوع کاربر خریدار', lambda p: p.buyer_user_type or "-"),
        'unique_delivery_id': ('شناسه یکتا تحویل', lambda p: p.unique_delivery_id or "-"),
        'delivery_address': ('آدرس تحویل', lambda p: p.delivery_address or "-"),
        'delivery_postal_code': ('کد پستی تحویل', lambda p: p.delivery_postal_code or "-"),
        'vehicle_type': ('نوع خودرو حمل', lambda p: p.vehicle_type or "-"),
    }
    
    # فقط ستون‌های انتخاب شده را اضافه می‌کنیم
    headers = []
    for col in selected_columns:
        if col in column_mapping:
            headers.append(column_mapping[col][0])
    
    # افزودن هدرها به اکسل
    ws.append(headers)
    
    ws.sheet_view.rightToLeft = True

    # داده‌ها
    for purchase in purchases:
        row = []
        for col in selected_columns:
            if col in column_mapping:
                try:
                    value = column_mapping[col][1](purchase)
                    row.append(value)
                except Exception as e:
                    logger.warning(f"خطا در استخراج مقدار {col} برای خرید {purchase.id}: {str(e)}")
                    row.append("-")
        
        ws.append(row)
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"purchases_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    logger.warning(filename)
    return response

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def cargo_products_list(request):
    """
    API برای دریافت لیست کوتاژها
    """
    logger.warning(f"کاربر {request.user.username} درخواست دریافت لیست کوتاژ (حذف شده!) کرد. {get_client_ip(request)}")
    return JsonResponse({'status': 'error', 'message': "error"}, status=500)
    try:
        # فیلتر بر اساس وضعیت فعال
        active_only = request.GET.get('active_only', '1') == '1'
        
        if active_only:
            cargos = CargoProduct.objects.filter(status=True).order_by('-created_at')
        else:
            cargos = CargoProduct.objects.all().order_by('-created_at')
        
        # جستجو بر اساس پارامتر search (اگر ارسال شده باشد)
        search_term = request.GET.get('search', '')
        if search_term:
            cargos = cargos.filter(
                Q(cottage__icontains=search_term) |
                Q(product_type__icontains=search_term) |
                Q(country__icontains=search_term) |
                Q(importer_name__icontains=search_term)
            )
        
        cargos_data = []
        for cargo in cargos:
            cargos_data.append({
                'id': cargo.id,
                'cottage': cargo.cottage,
                'type': cargo.type,
                'product_type': cargo.product_type,
                'product_type_display': cargo.get_product_type_display(),
                'country': cargo.country,
                'country_display': cargo.get_country_display(),
                'importer_name': cargo.importer_name,
                'weight': cargo.weight,
                'company_price': cargo.company_price,
                'customer_price': cargo.customer_price,
                'status': cargo.status
            })
            
        return JsonResponse({'status': 'success', 'cargos': cargos_data})
    
    except Exception as e:
        logger.warning(f"error cargo product {str(e)}")
        return JsonResponse({'status': 'error', 'message': "error"}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def cargo_product_details(request):
    """
    API برای دریافت جزئیات یک کوتاژ بر اساس شماره کوتاژ
    """
    cottage = request.GET.get('cottage', '')
    if not cottage:
        cottage = "0"
    logger.warning(f" (حذف شده!) دریافت جزئیات کوتاز {cottage} توسط {request.user.username} با آیپی {get_client_ip(request)}")
    return JsonResponse({'status': 'error', 'message': "error"}, status=500)
    try:
        cottage = request.GET.get('cottage', '')
        
        if not cottage:
            return JsonResponse({'status': 'error', 'message': 'شماره کوتاژ ارسال نشده است'}, status=400)
        
        try:
            cargo = CargoProduct.objects.get(cottage=cottage)
        except CargoProduct.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
        logger.warning(f"کوتاز: {cottage}")
        cargo_data = {
            'id': cargo.id,
            'cottage': cargo.cottage,
            'type': cargo.type,
            'product_type': cargo.product_type,
            'product_type_display': cargo.get_product_type_display(),
            'country': cargo.country,
            'country_display': cargo.get_country_display(),
            'importer_name': cargo.importer_name,
            'weight': cargo.weight,
            'company_price': cargo.company_price,
            'customer_price': cargo.customer_price,
            'status': cargo.status
        }
        
        return JsonResponse({'status': 'success', 'cargo': cargo_data})
    
    except Exception as e:
        logger.warning(f"error finding cargo product details: {str(e)}")
        return JsonResponse({'status': 'error', 'message': "error"}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager')
def bulk_edit_cargo(request):
    """
    API برای ویرایش گروهی کوتاژ
    """
    logger.warning(f"ویرایش گروهی (حذف شده!) کوتاژ توسط {request.user.username} با ایپی {get_client_ip(request)}")
    return JsonResponse({'status': 'error', 'message': "error"}, status=500)
    try:
        # دریافت لیست خریدهای انتخاب شده
        purchase_ids = request.POST.get('purchase_ids', '').split(',')
        purchase_ids = [pid for pid in purchase_ids if pid]
        
        if not purchase_ids:
            return JsonResponse({'status': 'error', 'message': 'هیچ خریدی انتخاب نشده است'}, status=400)
        
        # دریافت اطلاعات کوتاژ
        cargo_id = request.POST.get('cargo_id', '')
        cottage = request.POST.get('cottage', '')
        
        # حالت اول: استفاده از یک کوتاژ موجود
        if cargo_id:
            try:
                cargo = CargoProduct.objects.get(id=cargo_id)
            except CargoProduct.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
                
        # حالت دوم: ایجاد کوتاژ جدید
        elif cottage:
            # بررسی اینکه آیا کوتاژ قبلاً وجود دارد
            if CargoProduct.objects.filter(cottage=cottage).exists():
                return JsonResponse({'status': 'error', 'message': 'این شماره کوتاژ قبلاً ثبت شده است'}, status=400)
                
            # ایجاد کوتاژ جدید
            try:
                cargo = CargoProduct(
                    cottage=cottage,
                    type=request.POST.get('type', 'bazaargah'),
                    product_type=request.POST.get('product_type', 'corn'),
                    country=request.POST.get('country', 'iran'),
                    importer_name=request.POST.get('importer_name', ''),
                    weight=int(request.POST.get('weight', 100000) or 100000),
                    company_price=int(request.POST.get('company_price', 50000) or 50000),
                    customer_price=int(request.POST.get('customer_price', 50000) or 50000),
                    status=request.POST.get('status') == 'on'
                )
                cargo.save()
            except ValidationError as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد کوتاژ جدید: {str(e)}'}, status=500)
        else:
            return JsonResponse({'status': 'error', 'message': 'اطلاعات کوتاژ ناقص است'}, status=400)
        
        # اعمال کوتاژ به خریدهای انتخاب شده
        purchases = Purchase.objects.filter(id__in=purchase_ids)
        updated_count = 0
        
        for purchase in purchases:
            purchase.cargo = cargo
            purchase.save()
            updated_count += 1
            
            # ثبت در لاگ تغییرات
            old_cargo = 'بدون کوتاژ' if not hasattr(purchase, 'old_cargo') or purchase.old_cargo is None else purchase.old_cargo
            log_entry = PurchaseEditLog(
                purchase=purchase,
                user=request.user,
                field_name='cargo',
                old_value=old_cargo,
                new_value=str(cargo),
                edit_time=timezone.now()
            )
            log_entry.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'کوتاژ با موفقیت به {updated_count} خرید اختصاص داده شد',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def update_column_order(request):
    """
    ذخیره ترتیب جدید ستون‌ها
    """
    logger.warning(f"ذخیه ترتیب جدید ستون ها توسط {request.user.username} و آیپی {get_client_ip(request)}")
    try:
        data = json.loads(request.body)
        column_order = data.get('column_order', [])
        
        if not column_order:
            return JsonResponse({'status': 'error', 'message': 'ترتیب ستون‌ها ارسال نشده است'}, status=400)
        
        # ذخیره در سرور - ایجاد یا به‌روزرسانی تنظیمات کاربر
        user_role = determine_user_role(request.user)
        from ERP.models import ColumnOrderPreference
        
        # ایجاد یا به‌روزرسانی تنظیمات کاربر
        preference, created = ColumnOrderPreference.objects.get_or_create(
            user=request.user,
            user_role=user_role,
            defaults={
                'column_order': column_order
            }
        )
        
        if not created:
            # به‌روزرسانی تنظیمات موجود
            preference.column_order = column_order
            preference.save()
        
        # ذخیره در کوکی (به مدت 365 روز) برای سازگاری
        response = JsonResponse({'status': 'success'})
        response.set_cookie('purchase_list_column_order', json.dumps(column_order), max_age=30*24*60*60*12)
        
        return response
    except Exception as e:
        logger.error(f"error update column: {str(e)}")
        return JsonResponse({'status': 'error', 'message': "error"}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def get_column_order(request):
    """
    دریافت ترتیب ستون‌ها از سرور
    """
    logger.warning(f"دریافت ترتیب ستون ها توسط {request.user.username} و آیپی {get_client_ip(request)}")
    try:
        user_role = determine_user_role(request.user)
        
        # دریافت تنظیمات کاربر از سرور
        try:
            from ERP.models import ColumnOrderPreference
            preference = ColumnOrderPreference.objects.get(
                user=request.user,
                user_role=user_role
            )
            column_order = preference.column_order
        except ColumnOrderPreference.DoesNotExist:
            # اگر تنظیمات وجود نداشت، از ترتیب پیش‌فرض استفاده کن
            column_order = get_default_columns(user_role)
        
        return JsonResponse({
            'status': 'success',
            'column_order': column_order,
            'user_role': user_role
        })
        
    except Exception as e:
        logger.error(f"error getting column order: {str(e)}")
        return JsonResponse({'status': 'error', 'message': "error"}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def reset_column_order(request):
    """
    بازگرداندن ترتیب ستون‌ها به حالت پیش‌فرض
    """
    logger.warning(f"بازگرداندن ترتیب ستون ها به حالت پیش‌فرض توسط {request.user.username} و آیپی {get_client_ip(request)}")
    
    try:
        # تشخیص نقش کاربر و دریافت ستون‌های پیش‌فرض
        user_role = determine_user_role(request.user)
        default_columns = get_default_columns(user_role)
        
        # برای آسان‌تر کردن دیباگ
        print("Resetting column order to default:", default_columns)
        
        # حذف تنظیمات کاربر از دیتابیس
        from ERP.models import ColumnOrderPreference
        try:
            preference = ColumnOrderPreference.objects.get(
                user=request.user,
                user_role=user_role
            )
            preference.delete()
            print(f"Deleted existing preference for user {request.user.username} and role {user_role}")
        except ColumnOrderPreference.DoesNotExist:
            print(f"No existing preference found for user {request.user.username} and role {user_role}")
        
        # ایجاد پاسخ
        response = JsonResponse({
            'status': 'success', 
            'message': 'ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد',
            'column_order': default_columns
        })
        
        # حذف تمامی کوکی‌های مربوط به ستون‌ها
        response.delete_cookie('purchase_list_column_order')
        response.delete_cookie('selected_columns')
        
        # تنظیم مجدد کوکی‌ها با مقادیر پیش‌فرض
        response.set_cookie('selected_columns', ','.join(default_columns))
        
        return response
        
    except Exception as e:
        logger.error(f"Error in reset_column_order: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': f'خطا در بازگردانی ترتیب ستون‌ها: {str(e)}'
        }, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager')
def get_purchase_aggregated_stats(request):
    """
    API برای دریافت آمار اجماعی خریدهای انتخاب شده
    """
    logger.warning(f"دریافت آمار اجماعی خریدهای انتخاب شده توسط {request.user.username} و {get_client_ip(request)}")
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        hide_sensitive_info = user_role in ['sales_agent', 'support_agent']
        
        # دریافت لیست آیدی‌های خریدهای انتخاب شده
        purchase_ids = request.POST.get('purchase_ids', '').split(',')
        purchase_ids = [pid.strip() for pid in purchase_ids if pid.strip()]
        
        if not purchase_ids:
            return JsonResponse({
                'status': 'error', 
                'message': 'هیچ خریدی انتخاب نشده است'
            }, status=400)
        
        # دریافت خریدهای انتخاب شده
        purchases = Purchase.objects.filter(id__in=purchase_ids).select_related('customer', 'cargo').prefetch_related('customer__sales_agent', 'shenase_takhsis_set').order_by('-created_at')
        
        if not purchases.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'خریدهای انتخاب شده یافت نشدند'
            }, status=404)
        
        # محاسبه آمار
        stats = {
            'selected_count': purchases.count(),
            'total_order_weight': 0,
            'total_delivered_weight': 0,
            'avg_customer_price': 0,
            'customer_price_sum': 0,
            'valid_customer_price_count': 0
        }
        
        # اضافه کردن آمار حساس فقط برای نقش‌های مجاز
        if not hide_sensitive_info:
            stats.update({
                'total_amount_paid': 0,
                'avg_company_price': 0,
                'company_price_sum': 0,
                'valid_company_price_count': 0,
                'purchase_base_invoice': 0,  # فاکتور خرید مبنا
                'sales_base_invoice': 0,     # فاکتور فروش مبنا
                'profit': 0                  # سود
            })
        
        for purchase in purchases:
            # جمع‌آوری وزن‌ها
            if purchase.order_weight:
                stats['total_order_weight'] += purchase.order_weight
            
            if purchase.delivered_weight:
                stats['total_delivered_weight'] += purchase.delivered_weight
            
            # جمع‌آوری قیمت‌ها برای محاسبه میانگین
            if purchase.customer_price and purchase.customer_price > 0:
                stats['customer_price_sum'] += purchase.customer_price
                stats['valid_customer_price_count'] += 1
            
            # آمار حساس فقط برای نقش‌های مجاز
            if not hide_sensitive_info:
                # جمع‌آوری مبالغ
                if purchase.amount_paid:
                    stats['total_amount_paid'] += purchase.amount_paid
                
                if purchase.company_price and purchase.company_price > 0:
                    stats['company_price_sum'] += purchase.company_price
                    stats['valid_company_price_count'] += 1
                
                # محاسبه فاکتور خرید و فروش مبنا بر اساس فرمول جدید
                if purchase.company_price and purchase.customer_price:
                    # تعیین n بر اساس factor_code (که برابر با صدور فاکتور است)
                    # factor_code برابر با is_factored تنظیم می‌شود
                    factor_code = purchase.is_factored  # فاکتور مبنا = صدور فاکتور
                    n = 1 if factor_code else 0
                    
                    # وزن‌ها با مقدار پیش‌فرض 0 اگر None باشند
                    delivered_weight = purchase.delivered_weight or 0
                    order_weight = purchase.order_weight or 0
                    
                    # محاسبه فاکتور خرید مبنا
                    purchase_base = (n * purchase.company_price * delivered_weight) + ((1 - n) * purchase.company_price * order_weight)
                    stats['purchase_base_invoice'] += purchase_base
                    
                    # محاسبه فاکتور فروش مبنا
                    sales_base = (n * purchase.customer_price * delivered_weight) + ((1 - n) * purchase.customer_price * order_weight)
                    stats['sales_base_invoice'] += sales_base
        
        # محاسبه میانگین قیمت‌ها
        if stats['valid_customer_price_count'] > 0:
            stats['avg_customer_price'] = stats['customer_price_sum'] / stats['valid_customer_price_count']
        
        if not hide_sensitive_info:
            if stats['valid_company_price_count'] > 0:
                stats['avg_company_price'] = stats['company_price_sum'] / stats['valid_company_price_count']
            
            # محاسبه سود
            stats['profit'] = stats['sales_base_invoice'] - stats['purchase_base_invoice']
        
        # حذف فیلدهای کمکی
        del stats['customer_price_sum']
        del stats['valid_customer_price_count']
        
        if not hide_sensitive_info:
            del stats['company_price_sum']
            del stats['valid_company_price_count']
        
        return JsonResponse({
            'status': 'success',
            'stats': stats,
            'hide_sensitive_info': hide_sensitive_info
        })
        
    except Exception as e:
        logger.error(f"Error in get_purchase_aggregated_stats: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': f'خطا در محاسبه آمار:'
        }, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager')
def clear_column_cache(request):
    """
    پاک کردن cache و کوکی‌های مربوط به ستون‌ها
    """
    logger.warning(f"پاک کردن کش و کوکی ستون ها {request.user.username} و {get_client_ip(request)}")
    
    try:
        # ایجاد پاسخ
        response = JsonResponse({'status': 'success', 'message': 'کوکی‌ها با موفقیت پاک شدند'})
        
        # حذف تمامی کوکی‌های مربوط به ستون‌ها
        response.delete_cookie('selected_columns')
        response.delete_cookie('purchase_list_column_order')
        
        return response
    except Exception as e:
        logger.error(f"error in clearing column cahse: {str(e)}")
        return JsonResponse({'status': 'error', 'message': "error"}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager')
def get_section_purchase_ids(request):
    """
    API برای دریافت تمام ID های خریدهای یک بخش خاص (فعال، در انتظار پرداخت، آرشیو)
    """
    logger.warning(f"دریافت آیدی های خرید های بخش خاص توسط {request.user.username} و {get_client_ip(request)}")
    try:
        section = request.GET.get('section', 'active')  # active, pending, archived
        
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        # دریافت همان فیلترهای صفحه اصلی
        global_search = request.GET.get('global_search', '')
        customer = request.GET.get('customer', '')
        sales_agent = request.GET.get('sales_agent', '')
        if user_role == 'sales_agent':
            sales_agent = request.user.sales_agent.name
        invoice_id = request.GET.get('invoice_id', '')
        purchase_number = request.GET.get('purchase_number', '')
        cottage = request.GET.get('cottage', '')
        state = request.GET.get('state', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        is_archived = request.GET.get('is_archived', '')
        is_factored = request.GET.get('is_factored', '')
        is_urgent = request.GET.get('is_urgent', '')
        
        # ایجاد QuerySet پایه - فقط ID ها
        base_queryset = Purchase.objects.only('id').order_by('-created_at')
        
        # تقسیم‌بندی خریدها به سه دسته بر اساس section
        if section == 'active':
            # خریدهای فعال (به جز آرشیو و در انتظار پرداخت)
            queryset = base_queryset.exclude(state='ARCHIVED')\
                .exclude(is_archived=True)\
                .exclude(state__in=['SMS_SENT', 'INITIATED'])
        elif section == 'pending':
            # خریدهای در انتظار پرداخت
            queryset = base_queryset.filter(state__in=['SMS_SENT', 'INITIATED'])\
                .exclude(is_archived=True)
        elif section == 'archived':
            # خریدهای آرشیو شده
            queryset = base_queryset.filter(Q(state='ARCHIVED') | Q(is_archived=True))
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'بخش نامعتبر است'
            }, status=400)
        
        # فیلتر برای کارشناس فروش
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                queryset = queryset.filter(unique_sales_agent=request.user.sales_agent)
            else:
                queryset = Purchase.objects.none()
        
        # اگر فیلتر وضعیت آرشیو انتخاب شده است
        if is_archived != '':
            if is_archived == '1' and section != 'archived':
                queryset = Purchase.objects.none()
            elif is_archived == '0' and section == 'archived':
                queryset = Purchase.objects.none()
        
        # اعمال فیلترهای پیشرفته (همان فیلترهای صفحه اصلی)
        filters = Q()
        
        if customer:
            filters &= Q(customer__name__icontains=customer)
        
        if sales_agent:
            filters &= Q(unique_sales_agent__name__icontains=sales_agent)
        
        if invoice_id:
            filters &= Q(invoice_id__icontains=invoice_id)
        
        if purchase_number:
            filters &= Q(purchase_number__icontains=purchase_number)
        
        if cottage:
            filters &= Q(cargo__cottage__icontains=cottage)
        
        if state:
            filters &= Q(state=state)
        
        # فیلتر تاریخ
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                filters &= Q(created_at__date__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                filters &= Q(created_at__date__lte=date_to_obj)
            except ValueError:
                pass
        
        # فیلترهای اضافی
        if is_factored != '':
            filters &= Q(is_factored=(is_factored == '1'))
        
        if is_urgent == '1':
            filters &= Q(is_urgent=True)
        
        # اعمال فیلتر جستجوی سریع - جستجو در همه فیلدهای مهم
        if global_search:
            search_filters = get_allowed_search_filters(global_search, request)
            filters &= search_filters
        
        # اعمال همه فیلترها
        if filters:
            queryset = queryset.filter(filters)
        
        # دریافت تمام ID ها (محدودیت برای جلوگیری از overload)
        purchase_ids = list(queryset.values_list('id', flat=True)[:5000])  # حداکثر 5000
        
        return JsonResponse({
            'status': 'success',
            'purchase_ids': purchase_ids,
            'count': len(purchase_ids),
            'section': section
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت ایدی بخش خرید آیدی ها {str(e)}, {section}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت لیست خریدها: {str(e)}'
        }, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def get_purchase_table_configuration(request):
    """
    API برای دریافت تنظیمات ستون‌های جدول خریدها
    """
    logger.warning(f"دریافت تنظیمات ستون‌های جدول خریدها (حذف شده!) توسط {request.user.username} و {get_client_ip(request)}")
    return JsonResponse({
            'status': 'error',
            'message': "error"
        }, status=500)
    try:
        table_name = request.GET.get('table_name', 'purchases')
        user_role = determine_user_role(request.user)
        
        # تعریف ستون‌های مختلف بر اساس نقش کاربر
        if user_role in ['sales_agent', 'support_agent']:
            # ستون‌های محدود برای کارشناسان فروش و پیگیری
            columns = [
                {'id': 'purchase_number', 'name': 'شماره خرید', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'customer', 'name': 'نام مشتری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'buyer_name', 'name': 'نام خریدار', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'date', 'name': 'تاریخ', 'type': 'date', 'filterable': True, 'sortable': True},
                {'id': 'weight', 'name': 'وزن خرید', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'customer_price', 'name': 'فی فروش', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'cargo', 'name': 'کوتاژ', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'product_type', 'name': 'نام محصول', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'customer_phones', 'name': 'تلفن های مشتری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'status', 'name': 'وضعیت', 'type': 'choice', 'filterable': True, 'sortable': True},
            ]
        else:
            # ستون‌های کامل برای سایر نقش‌ها
            columns = [
                {'id': 'purchase_number', 'name': 'شماره خرید', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'date', 'name': 'تاریخ', 'type': 'date', 'filterable': True, 'sortable': True},
                {'id': 'customer', 'name': 'نام مشتری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'invoice_id', 'name': 'کد درون سازمانی', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'sales_agent', 'name': 'نماینده فروش', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'weight', 'name': 'وزن', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'cargo', 'name': 'کوتاژ', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'importer', 'name': 'واردکننده', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'status', 'name': 'وضعیت‌ها', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'company_price', 'name': 'فی خرید', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'customer_price', 'name': 'فی فروش', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'amount_paid', 'name': 'مبلغ پرداختی', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'is_factored', 'name': 'ثبت فاکتور', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'is_urgent', 'name': 'فوری', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'is_canceled', 'name': 'لغو شده', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'is_archived', 'name': 'آرشیو شده', 'type': 'boolean', 'filterable': True, 'sortable': True},
                # ستون‌های اضافی
                {'id': 'address', 'name': 'آدرس', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'description', 'name': 'توضیحات', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'factor_code', 'name': 'فاکتور مبنا', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'tracking_number', 'name': 'شماره پیگیری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'shenase_takhsis', 'name': 'شناسه‌های تخصیص', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'code_melli_tahvil', 'name': 'کد ملی تحویل', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'bazaargah_phone_number', 'name': 'شماره تلفن بازارگاه', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'buyer_name', 'name': 'نام خریدار', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'send_cottage_sms', 'name': 'ارسال پیامک کوتاژ', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'total_weight', 'name': 'وزن کل', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'type', 'name': 'نوع خرید', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'payment_method', 'name': 'شیوه پرداخت', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'updated_at', 'name': 'تاریخ بروزرسانی', 'type': 'date', 'filterable': True, 'sortable': True},
                {'id': 'is_weight_costed', 'name': 'کسر از وزن موجود', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'is_ap_af', 'name': 'اتوکامپلیت شده', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'extelaf_weight', 'name': 'وزن اختلاف', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'priority', 'name': 'اولویت', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'priority_reason', 'name': 'دلیل اولویت', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'barbary', 'name': 'نام باربری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'barbary_phone', 'name': 'شماره باربری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'product_type', 'name': 'نام محصول', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'customer_phones', 'name': 'تلفن های مشتری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'first_barnameh_date', 'name': 'تاریخ اولین بارنامه', 'type': 'date', 'filterable': True, 'sortable': True},
                {'id': 'last_barnameh_date', 'name': 'تاریخ آخرین بارنامه', 'type': 'date', 'filterable': True, 'sortable': True},
                {'id': 'ready_for_invoice', 'name': 'آماده فاکتور', 'type': 'boolean', 'filterable': True, 'sortable': True},
                {'id': 'purchase_mabna_invoice', 'name': 'فاکتور خرید مبنا', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'sales_mabna_invoice', 'name': 'فاکتور فروش مبنا', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'mabna_profit', 'name': 'سود مبنا', 'type': 'number', 'filterable': True, 'sortable': True},
                {'id': 'barbary_confidential_number', 'name': 'شماره باربری محرمانه', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'barbary_customer_number', 'name':'شماره باربری مشتری', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'delivery_receiver_name', 'name':'نام تحویل گیرنده', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'buyer_national_id', 'name':'شناسه ملی خریدار', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'buyer_user_type', 'name':'نوع کاربری خریدار', 'type': 'choice', 'filterable': True, 'sortable': True},
                {'id': 'unique_delivery_id', 'name':'شناسه یکتا تحویل', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'delivery_address', 'name':'آدرس تحویل', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'delivery_postal_code', 'name':'کد پستی تحویل', 'type': 'text', 'filterable': True, 'sortable': True},
                {'id': 'vehicle_type', 'name':'نوع خودرو حمل', 'type': 'choice', 'filterable': True, 'sortable': True},
            ]
        
        return JsonResponse({
            'status': 'success',
            'columns': columns,
            'table_name': table_name
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
@login_required
def apply_purchase_filter(request):
    """
    API برای اعمال فیلتر سمت سرور به خریدها
    """
    logger.warning(f"درخواست فیلتر خرید توسط {request.user.username} انجام شده. {get_client_ip(request)}")
    logger.warning(f"apply purchase filter")
    try:
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        
        sort_config = json.loads(request.POST.get('sort', '{}'))
        # دریافت پارامترهای pagination با validation بیشتر
        page_param = request.POST.get('page', '1')
        per_page_param = request.POST.get('per_page', '50')
        section = request.POST.get('section', 'active')  # active, pending, archived
        # دریافت پارامتر جستجوی سریع
        global_search = request.POST.get('global_search', '')
        
        try:
            page = int(page_param)
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            logger.error(f"❌ مقادیر pagination نامعتبر: page={page_param}, per_page={per_page_param}")
            page = 1
            per_page = 50
        
        
        
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        # فیلدهای ضروری برای QuerySet
        selected_fields = [
            'id', 'created_at', 'updated_at', 'purchase_number', 'invoice_id', 
            'order_weight', 'delivered_weight', 'state', 'is_factored', 'is_urgent', 
            'is_canceled', 'is_archived', 'company_price', 'customer_price', 
            'amount_paid', 'factor_code', 'buyer_name', 'ready_for_invoice',
            'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit',
            'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'description',
            'is_fully_tasvied', 'bazaargah_phone_number', 'tahvil_phone_number', 
            'code_melli_tahvil', 'address',
            # فیلدهای جدید اضافه شده
            'barbary_confidential_number', 'barbary_customer_number', 'delivery_receiver_name',
            'buyer_national_id', 'buyer_user_type', 'unique_delivery_id', 
            'delivery_address', 'delivery_postal_code', 'vehicle_type'
        ]
        
        # فیلدهای customer و cargo
        customer_fields = ['customer__id', 'customer__name']
        cargo_fields = ['cargo__id', 'cargo__cottage', 'cargo__product_type', 'cargo__barbary__name', 'cargo__barbary__phone_number', 'cargo__vared_konandeh__name']
        sales_agent_fields = ['unique_sales_agent__id', 'unique_sales_agent__name']
        
        all_fields = selected_fields + customer_fields + cargo_fields + sales_agent_fields
        
        # ایجاد QuerySet پایه
        base_queryset = Purchase.objects.select_related(
            'customer', 'cargo', 'unique_sales_agent', 
            'cargo__vared_konandeh', 'cargo__barbary'
        ).prefetch_related('shenase_takhsis_set')
        
        # تقسیم‌بندی بر اساس section
        if section == 'active':
            queryset = base_queryset.exclude(state='ARCHIVED')\
                .exclude(is_archived=True)\
                .exclude(state__in=['SMS_SENT', 'INITIATED'])
        elif section == 'pending':
            queryset = base_queryset.filter(state__in=['SMS_SENT', 'INITIATED'])\
                .exclude(is_archived=True)
        elif section == 'archived':
            queryset = base_queryset.filter(Q(state='ARCHIVED') | Q(is_archived=True))
        else:
            queryset = base_queryset
        
        # فیلتر برای کارشناس فروش
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                queryset = queryset.filter(unique_sales_agent=request.user.sales_agent)
            else:
                queryset = Purchase.objects.none()
        

        
        # اعمال فیلترها - فقط اگر فیلتر وجود داشته باشد
        if filters:
            filter_conditions = Q()
            
            for column_id, filter_data in filters.items():
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                

                
                if column_id == 'purchase_number':
                    # حذف مقادیر خالی
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(purchase_number__in=values)
                        
                elif column_id == 'customer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(customer__name__in=values)
                        else:
                            filter_conditions &= ~Q(customer__name__in=values)
                        
                elif column_id == 'invoice_id':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(invoice_id__in=values)
                        else:
                            filter_conditions &= ~Q(invoice_id__in=values)
                        
                elif column_id == 'sales_agent':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(unique_sales_agent__name__in=values)
                        else:
                            filter_conditions &= ~Q(unique_sales_agent__name__in=values)
                        
                elif column_id == 'cargo':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__cottage__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__cottage__in=values)
                        
                elif column_id == 'status':
                    # تبدیل نمایش وضعیت به کد وضعیت
                    status_map = {v: k for k, v in dict(Purchase.STATUS_CHOICES).items()}
                    status_codes = []
                    for v in values:
                        if v in status_map:
                            status_codes.append(status_map[v])
                        else:
                            # اگر مقدار مستقیماً کد باشد
                            status_codes.append(v)
                    
                    if status_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(state__in=status_codes)
                        else:
                            filter_conditions &= ~Q(state__in=status_codes)
                        
                elif column_id in ['is_factored', 'is_urgent', 'is_canceled', 'is_archived']:
                    bool_values = []
                    for v in values:
                        if v.lower() in ['بله', 'true', '1', 'yes']:
                            bool_values.append(True)
                        elif v.lower() in ['خیر', 'false', '0', 'no']:
                            bool_values.append(False)
                    
                    if bool_values:
                        field_name = column_id
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{field_name}__in': bool_values})
                        else:
                            filter_conditions &= ~Q(**{f'{field_name}__in': bool_values})
                        
                elif column_id in ['weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid']:
                    # فیلتر عددی - تبدیل رشته‌ها به عدد
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                # حذف کاما و تبدیل به عدد
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        if numeric_values:
                            field_mapping = {
                                'weight': 'order_weight',
                                'delivered_weight': 'delivered_weight',
                                'company_price': 'company_price',
                                'customer_price': 'customer_price',
                                'amount_paid': 'amount_paid'
                            }
                            
                            field_name = field_mapping.get(column_id, column_id)
                            
                            if filter_type == 'include':
                                filter_conditions &= Q(**{f'{field_name}__in': numeric_values})
                            else:
                                filter_conditions &= ~Q(**{f'{field_name}__in': numeric_values})
                                
                    except (ValueError, TypeError) as e:

                        continue
                        
                elif column_id == 'date':
                    # فیلتر تاریخی
                    try:
                        date_conditions = Q()
                        for date_str in values:
                            if date_str and date_str.strip():
                                # تبدیل تاریخ فارسی به تاریخ میلادی
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts) == 3:
                                        # فرض: فرمت سال/ماه/روز
                                        year, month, day = parts
                                        date_obj = datetime(int(year), int(month), int(day)).date()
                                        date_conditions |= Q(created_at__date=date_obj)
                        
                        if date_conditions:
                            if filter_type == 'include':
                                filter_conditions &= date_conditions
                            else:
                                filter_conditions &= ~date_conditions
                                
                    except (ValueError, TypeError) as e:

                        continue
                
                # فیلترهای جدید
                elif column_id == 'importer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__vared_konandeh__name__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__vared_konandeh__name__in=values)
                
                elif column_id == 'barbary':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__barbary__name__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__barbary__name__in=values)
                
                elif column_id in ['address', 'description', 'unique_buyer_id', 'code_melli_tahvil', 
                                 'bazaargah_phone_number', 'tahvil_phone_number', 'priority_reason', 'factor_status']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': values})
                
                elif column_id in ['factor_code', 'send_cottage_sms', 'is_weight_costed', 
                                 'is_ap_af', 'is_fully_tasvied', 'ready_for_invoice']:
                    bool_values = []
                    for v in values:
                        if v in ['بله', 'فعال', True, 'true', '1']:
                            bool_values.append(True)
                        elif v in ['خیر', 'غیرفعال', False, 'false', '0']:
                            bool_values.append(False)
                    
                    if bool_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': bool_values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': bool_values})
                
                elif column_id in ['total_weight', 'extelaf_weight', 'extelaf_amount', 
                                 'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit']:
                    # فیلترهای عددی اضافی
                    numeric_values = []
                    for v in values:
                        try:
                            clean_value = str(v).replace(',', '').strip()
                            if clean_value:
                                numeric_values.append(float(clean_value))
                        except (ValueError, TypeError):
                            continue
                    
                    if numeric_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': numeric_values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': numeric_values})
                
                elif column_id in ['type', 'payment_method', 'extelaf_type', 'priority']:
                    # فیلترهای choice
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': values})
                
                elif column_id == 'shenase_takhsis':
                    # فیلتر برای شناسه‌های تخصیص
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(shenase_takhsis_set__code__in=values)
                        else:
                            filter_conditions &= ~Q(shenase_takhsis_set__code__in=values)
                
                elif column_id == 'updated_at':
                    # فیلتر تاریخ بروزرسانی
                    try:
                        date_conditions = Q()
                        for date_str in values:
                            if date_str and date_str.strip():
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts) == 3:
                                        year, month, day = parts
                                        date_obj = datetime(int(year), int(month), int(day)).date()
                                        date_conditions |= Q(updated_at__date=date_obj)
                        
                        if date_conditions:
                            if filter_type == 'include':
                                filter_conditions &= date_conditions
                            else:
                                filter_conditions &= ~date_conditions
                                
                    except (ValueError, TypeError) as e:

                        continue
            
            # اعمال فیلترها اگر وجود داشته باشند
            if filter_conditions:
                queryset = queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع (global search) اگر وجود داشته باشد
        if global_search and global_search.strip():
            global_search_filters = (
                # اطلاعات اصلی خرید
                Q(customer__name__icontains=global_search) |
                Q(purchase_number__icontains=global_search) |
                Q(invoice_id__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                
                # اطلاعات کوتاژ و حمل‌ونقل
                Q(cargo__cottage__icontains=global_search) |
                Q(cargo__vared_konandeh__name__icontains=global_search) |
                Q(cargo__barbary__name__icontains=global_search) |
                
                # اطلاعات تماس و آدرس
                Q(address__icontains=global_search) |
                Q(bazaargah_phone_number__icontains=global_search) |
                Q(tahvil_phone_number__icontains=global_search) |
                Q(code_melli_tahvil__icontains=global_search) |
                Q(factor_status__icontains=global_search) |
                # اطلاعات ردیابی
                Q(unique_buyer_id__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |

                
                # توضیحات و اطلاعات اضافی
                Q(description__icontains=global_search) |
                Q(priority_reason__icontains=global_search) |
                
                # فیلدهای جدید حمل و نقل
                Q(barbary_confidential_number__icontains=global_search) |
                Q(barbary_customer_number__icontains=global_search) |
                Q(delivery_receiver_name__icontains=global_search) |
                Q(buyer_national_id__icontains=global_search) |
                Q(unique_delivery_id__icontains=global_search) |
                Q(delivery_address__icontains=global_search) |
                Q(delivery_postal_code__icontains=global_search) |
                
                # نماینده فروش
                Q(unique_sales_agent__name__icontains=global_search)
            )
            queryset = queryset.filter(global_search_filters)
        
        # اعمال مرتب‌سازی
        if sort_config.get('column') and sort_config.get('direction'):
            column = sort_config['column']
            direction = sort_config['direction']
            
            # نقشه‌برداری ستون‌ها به فیلدهای مدل
            sort_mapping = {
                'purchase_number': 'purchase_number',
                'date': 'created_at',
                'customer': 'customer__name',
                'invoice_id': 'invoice_id',
                'sales_agent': 'unique_sales_agent__name',
                'weight': 'order_weight',
                'cargo': 'cargo__cottage',
                'importer': 'cargo__vared_konandeh__name',
                'barbary': 'cargo__barbary__name',
                'status': 'state',
                'company_price': 'company_price',
                'customer_price': 'customer_price',
                'amount_paid': 'amount_paid',
                'delivered_weight': 'delivered_weight',
                'total_weight': 'total_weight',
                'is_factored': 'is_factored',
                'is_urgent': 'is_urgent',
                'is_canceled': 'is_canceled',
                'is_archived': 'is_archived',
                'is_fully_tasvied': 'is_fully_tasvied',
                'address': 'address',
                'description': 'description',
                'factor_code': 'factor_code',
                'unique_buyer_id': 'unique_buyer_id',
                'code_melli_tahvil': 'code_melli_tahvil',
                'bazaargah_phone_number': 'bazaargah_phone_number',
                'buyer_name': 'buyer_name',
                'tahvil_phone_number': 'tahvil_phone_number',
                'send_cottage_sms': 'send_cottage_sms',
                'type': 'type',
                'payment_method': 'payment_method',
                'updated_at': 'updated_at',
                'is_weight_costed': 'is_weight_costed',
                'is_ap_af': 'is_ap_af',
                'extelaf_type': 'extelaf_type',
                'extelaf_weight': 'extelaf_weight',
                'extelaf_amount': 'extelaf_amount',
                'priority': 'priority',
                'priority_reason': 'priority_reason',
                'ready_for_invoice': 'ready_for_invoice',
                'purchase_mabna_invoice': 'purchase_mabna_invoice',
                'sales_mabna_invoice': 'sales_mabna_invoice',
                'mabna_profit': 'mabna_profit',
                'details': 'id',  # مرتب‌سازی بر اساس ID
                'جزئیات': 'id',  # مرتب‌سازی بر اساس ID
                'actions': 'id',  # مرتب‌سازی بر اساس ID
                'عملیات': 'id',  # مرتب‌سازی بر اساس ID
                # فیلدهای جدید برای مرتب‌سازی
                'barbary_confidential_number': 'barbary_confidential_number',
                'barbary_customer_number': 'barbary_customer_number',
                'delivery_receiver_name': 'delivery_receiver_name',
                'buyer_national_id': 'buyer_national_id',
                'buyer_user_type': 'buyer_user_type',
                'unique_delivery_id': 'unique_delivery_id',
                'delivery_address': 'delivery_address',
                'delivery_postal_code': 'delivery_postal_code',
                'vehicle_type': 'vehicle_type',
                'factor_status': 'factor_status',
            }
            
            sort_field = sort_mapping.get(column, column)
            if direction == 'desc':
                sort_field = f'-{sort_field}'
                
            queryset = queryset.order_by(sort_field)
        else:
            # مرتب‌سازی پیش‌فرض
            queryset = queryset.order_by('-created_at')
        
        # Pagination - درست اعمال pagination
        total_count_before_pagination = queryset.count()
        
        paginator = Paginator(queryset, per_page)
        
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage) as e:
            page_obj = paginator.page(1)
            page = 1
        
        # بررسی اضافی برای اطمینان از صحت pagination
        if page_obj.object_list.count() == 0 and page > 1:
            try:
                page_obj = paginator.page(paginator.num_pages)
            except EmptyPage:
                page_obj = paginator.page(1)
        
        # تبدیل داده‌ها به JSON - فقط آیتم‌های صفحه فعلی
        purchases_data = []
        for purchase in page_obj.object_list:
            data = {
                'id': purchase.id,
                'purchase_number': purchase.purchase_number or 'تعیین نشده',
                'date': purchase.created_at.strftime("%Y/%m/%d") if purchase.created_at else '-',
                'customer': purchase.customer.name if purchase.customer else 'نامشخص',
                'invoice_id': purchase.invoice_id or 'تعیین نشده',
                'sales_agent': purchase.unique_sales_agent.name if purchase.unique_sales_agent else '-',
                'weight': f"{purchase.order_weight:,}" if purchase.order_weight else '0',
                'cargo': purchase.cargo.cottage if purchase.cargo else '-',
                'barbary': purchase.cargo.barbary.name if purchase.cargo and purchase.cargo.barbary else '-',
                'importer': purchase.cargo.vared_konandeh.name if purchase.cargo and purchase.cargo.vared_konandeh else '-',
                'address': purchase.address or '-',
                'description': purchase.description or '-',
                'factor_code': '1' if purchase.factor_code else '0',
                'unique_buyer_id': purchase.unique_buyer_id or '-',
                'factor_status': purchase.factor_status or '-',
                'code_melli_tahvil': purchase.code_melli_tahvil or '-',
                'bazaargah_phone_number': purchase.bazaargah_phone_number or '-',
                'tahvil_phone_number': purchase.tahvil_phone_number or '-',
                'send_cottage_sms': 'بله' if purchase.send_cottage_sms else 'خیر',
                'total_weight': f"{purchase.total_weight:,}" if purchase.total_weight else '-',
                'type': purchase.get_type_display() if purchase.type else '-',
                'payment_method': purchase.get_payment_method_display() if purchase.payment_method else '-',
                'updated_at': purchase.updated_at.strftime("%Y/%m/%d") if purchase.updated_at else '-',
                'is_weight_costed': 'بله' if purchase.is_weight_costed else 'خیر',
                'is_ap_af': 'بله' if purchase.is_ap_af else 'خیر',
                'extelaf_type': purchase.get_extelaf_type_display() if purchase.extelaf_type else '-',
                'extelaf_weight': f"{purchase.extelaf_weight:,}" if purchase.extelaf_weight else '-',
                'extelaf_amount': f"{purchase.extelaf_amount:,}" if purchase.extelaf_amount else '-',
                'is_fully_tasvied': 'بله' if purchase.is_fully_tasvied else 'خیر',
                'priority': purchase.priority or '-',
                'priority_reason': purchase.priority_reason or '-',
                'status': purchase.get_state_display() if purchase.state else '-',
                'delivered_weight': f"{purchase.delivered_weight:,}" if purchase.delivered_weight else '0',
                'is_factored': 'بله' if purchase.is_factored else 'خیر',
                'is_urgent': 'بله' if purchase.is_urgent else 'خیر',
                'is_canceled': 'بله' if purchase.is_canceled else 'خیر',
                'is_archived': 'بله' if purchase.is_archived else 'خیر',
                'buyer_name': purchase.buyer_name or '-',
                'ready_for_invoice': 'بله' if purchase.ready_for_invoice else 'خیر',
                # فیلدهای جدید اضافه شده
                'barbary_confidential_number': purchase.barbary_confidential_number or '-',
                'barbary_customer_number': purchase.barbary_customer_number or '-',
                'delivery_receiver_name': purchase.delivery_receiver_name or '-',
                'buyer_national_id': purchase.buyer_national_id or '-',
                'buyer_user_type': purchase.get_buyer_user_type_display() if purchase.buyer_user_type else '-',
                'unique_delivery_id': purchase.unique_delivery_id or '-',
                'delivery_address': purchase.delivery_address or '-',
                'delivery_postal_code': purchase.delivery_postal_code or '-',
                'vehicle_type': purchase.get_vehicle_type_display() if purchase.vehicle_type else '-',
                # shenase_takhsis - نیاز به پردازش خاص دارد
                'shenase_takhsis': ', '.join([s.code for s in purchase.shenase_takhsis_set.all()]) if purchase.shenase_takhsis_set.exists() else '-',
                # ستون جزئیات - فقط برای شناسایی در frontend
                'details': f'جزئیات خرید {purchase.id}',
                'جزئیات': f'جزئیات خرید {purchase.id}',
                'actions': f'عملیات خرید {purchase.id}',
                'عملیات': f'عملیات خرید {purchase.id}',
                # اضافه کردن داده‌های raw برای محاسبات
                'raw_order_weight': purchase.order_weight or 0,
                'raw_delivered_weight': purchase.delivered_weight or 0,
                'raw_is_factored': purchase.is_factored,
            }
            
            # فیلدهای حساس فقط برای نقش‌های مجاز
            if user_role not in ['sales_agent', 'support_agent']:
                data.update({
                    'company_price': f"{purchase.company_price:,}" if purchase.company_price else '0',
                    'customer_price': f"{purchase.customer_price:,}" if purchase.customer_price else '0',
                    'amount_paid': f"{purchase.amount_paid:,}" if purchase.amount_paid else '0',
                    'purchase_mabna_invoice': f"{purchase.purchase_mabna_invoice:,}" if purchase.purchase_mabna_invoice else '-',
                    'sales_mabna_invoice': f"{purchase.sales_mabna_invoice:,}" if purchase.sales_mabna_invoice else '-',
                    'mabna_profit': f"{purchase.mabna_profit:,}" if purchase.mabna_profit else '-',
                    'raw_company_price': purchase.company_price or 0,
                    'raw_customer_price': purchase.customer_price or 0,
                    'raw_amount_paid': purchase.amount_paid or 0,
                })
            else:
                data.update({
                    'customer_price': f"{purchase.customer_price:,}" if purchase.customer_price else '0',
                    'raw_customer_price': purchase.customer_price or 0,
                    # فیلدهای غیرحساس که برای کاربران محدود قابل مشاهده هستند
                    'purchase_mabna_invoice': '-',  # مخفی شده
                    'sales_mabna_invoice': '-',     # مخفی شده  
                    'mabna_profit': '-',            # مخفی شده
                    
                })

            allowed_fields = get_allowed_columns(user_role)
            # فقط کلیدهایی که در allowed_fields هستند را نگه می‌داریم
            data = {k: v for k, v in data.items() if k in allowed_fields}
            data.update({
                'details': f'جزئیات خرید {purchase.id}',
                'جزئیات': f'جزئیات خرید {purchase.id}',
                'actions': f'عملیات خرید {purchase.id}',
                'عملیات': f'عملیات خرید {purchase.id}',
                'id': purchase.id,
            })
            
            
            purchases_data.append(data)
        

        
        # ایجاد pagination response با اطلاعات کامل
        pagination_response = {
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'number': page_obj.number,
            'num_pages': paginator.num_pages,
            'count': paginator.count,
        }
        
        # اضافه کردن page_range برای pagination UI
        try:
            pagination_response['page_range'] = list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1))
        except Exception as e:
            # fallback: محدوده ساده
            start_page = max(1, page_obj.number - 2)
            end_page = min(paginator.num_pages, page_obj.number + 2)
            pagination_response['page_range'] = list(range(start_page, end_page + 1))
        
        return JsonResponse({
            'status': 'success',
            'data': purchases_data,
            'pagination': pagination_response,
            'total_count': queryset.count(),
            'filtered_count': paginator.count,
            'section': section,
            'debug': {
                'requested_page': page,
                'actual_page': page_obj.number,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'items_in_page': len(purchases_data)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
@login_required
def get_purchase_column_values(request):
    """
    API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر
    """
    from core.PurchaseModel import Purchase
    
    logger.warning(f"API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر توسط {request.user.username} دسترسی یافت. {get_client_ip(request)}")
    try:
        column_id = request.POST.get('column_id')
        section = request.POST.get('section', 'active')
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
        
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        allowed_fields = get_allowed_columns(user_role)
        if column_id not in allowed_fields:
            return JsonResponse({
                'status': 'error',
                'message': 'شما اجازه دسترسی به این ستون را ندارید'
            }, status=403)
        
        # ایجاد QuerySet پایه
        base_queryset = Purchase.objects.select_related(
            'customer', 'cargo', 'unique_sales_agent', 
            'cargo__vared_konandeh', 'cargo__barbary'
        ).prefetch_related('shenase_takhsis_set')

        
        # تقسیم‌بندی بر اساس section
        if section == 'active':
            queryset = base_queryset.exclude(state='ARCHIVED')\
                .exclude(is_archived=True)\
                .exclude(state__in=['SMS_SENT', 'INITIATED'])
        elif section == 'pending':
            queryset = base_queryset.filter(state__in=['SMS_SENT', 'INITIATED'])\
                .exclude(is_archived=True)
        elif section == 'archived':
            queryset = base_queryset.filter(Q(state='ARCHIVED') | Q(is_archived=True))
        else:
            queryset = base_queryset
        
        # فیلتر برای کارشناس فروش
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                queryset = queryset.filter(unique_sales_agent=request.user.sales_agent)
            else:
                queryset = Purchase.objects.none()
        
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
                
                if filter_column_id == 'purchase_number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(purchase_number__in=values)
                        
                elif filter_column_id == 'customer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(customer__name__in=values)
                        else:
                            filter_conditions &= ~Q(customer__name__in=values)
                        
                elif filter_column_id == 'invoice_id':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(invoice_id__in=values)
                        else:
                            filter_conditions &= ~Q(invoice_id__in=values)
                        
                elif filter_column_id == 'sales_agent':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(unique_sales_agent__name__in=values)
                        else:
                            filter_conditions &= ~Q(unique_sales_agent__name__in=values)
                        
                elif filter_column_id == 'cargo':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__cottage__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__cottage__in=values)
                        
                elif filter_column_id == 'status':
                    # تبدیل نمایش وضعیت به کد وضعیت
                    status_map = {v: k for k, v in dict(Purchase.STATUS_CHOICES).items()}
                    status_codes = []
                    for v in values:
                        if v in status_map:
                            status_codes.append(status_map[v])
                        else:
                            # جستجوی معکوس - اگر کد وضعیت ارسال شده
                            status_codes.append(v)
                    
                    if status_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(state__in=status_codes)
                        else:
                            filter_conditions &= ~Q(state__in=status_codes)
                
                # فیلترهای بولین
                elif filter_column_id in ['is_factored', 'is_urgent', 'is_canceled', 'is_archived']:
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
                
                # فیلترهای عددی
                elif filter_column_id in ['weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid']:
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
                        field_mapping = {
                            'weight': 'order_weight',
                            'delivered_weight': 'delivered_weight',
                            'company_price': 'company_price',
                            'customer_price': 'customer_price',
                            'amount_paid': 'amount_paid'
                        }
                        field_name = field_mapping.get(filter_column_id, filter_column_id)
                        
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{field_name}__in': numeric_values})
                        else:
                            filter_conditions &= ~Q(**{f'{field_name}__in': numeric_values})
                
                # فیلتر تاریخ
                elif filter_column_id == 'date':
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
                            filter_conditions &= Q(created_at__date__in=date_values)
                        else:
                            filter_conditions &= ~Q(created_at__date__in=date_values)
                
                elif filter_column_id == 'buyer_name':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(buyer_name__in=values)
                        else:
                            filter_conditions &= ~Q(buyer_name__in=values)
                
                # فیلترهای فعلی برای ستون‌های جدید در get_purchase_column_values
                elif filter_column_id == 'importer':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__vared_konandeh__name__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__vared_konandeh__name__in=values)
                
                elif filter_column_id == 'barbary':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__barbary__name__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__barbary__name__in=values)
                
                elif filter_column_id == 'barbary_phone':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__barbary__phone_number__in=values)
                        else:
                            filter_conditions &= ~Q(cargo__barbary__phone_number__in=values)
                
                elif filter_column_id == 'product_type':
                    # تبدیل نمایش فارسی به کد محصول
                    from core.CargoProductModel import CargoProduct
                    product_map = {v: k for k, v in dict(CargoProduct.PRODUCT_TYPES).items()}
                    product_codes = []
                    for v in values:
                        if v in product_map:
                            product_codes.append(product_map[v])
                        else:
                            product_codes.append(v)
                    
                    if product_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(cargo__product_type__in=product_codes)
                        else:
                            filter_conditions &= ~Q(cargo__product_type__in=product_codes)
                
                
                elif filter_column_id in ['first_barnameh_date', 'last_barnameh_date']:
                    date_values = []
                    for v in values:
                        try:
                            if '/' in v:
                                date_obj = datetime.strptime(v, "%Y/%m/%d").date()
                                date_values.append(date_obj)
                        except (ValueError, TypeError):
                            continue
                    
                    if date_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(barnamehs__barnameh_date__in=date_values)
                        else:
                            filter_conditions &= ~Q(barnamehs__barnameh_date__in=date_values)
                
                elif filter_column_id in ['address', 'description', 'unique_buyer_id', 
                                        'code_melli_tahvil', 'bazaargah_phone_number', 
                                        'tahvil_phone_number', 'priority_reason',
                                        'barbary_confidential_number', 'barbary_customer_number',
                                        'delivery_receiver_name', 'buyer_national_id', 'unique_delivery_id',
                                        'delivery_address', 'delivery_postal_code', 'factor_status']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{filter_column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{filter_column_id}__in': values})
                
                elif filter_column_id == 'buyer_user_type':
                    # تبدیل نمایش فارسی به کد نوع کاربری
                    from core.CustomerModel import FIELD_OF_ACTIVITY
                    user_type_map = {v: k for k, v in dict(FIELD_OF_ACTIVITY).items()}
                    user_type_codes = []
                    for v in values:
                        if v in user_type_map:
                            user_type_codes.append(user_type_map[v])
                        else:
                            user_type_codes.append(v)
                    
                    if user_type_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(buyer_user_type__in=user_type_codes)
                        else:
                            filter_conditions &= ~Q(buyer_user_type__in=user_type_codes)
                
                elif filter_column_id == 'vehicle_type':
                    # تبدیل نمایش فارسی به کد نوع خودرو
                    from core.PurchaseModel import Purchase
                    vehicle_type_map = {v: k for k, v in dict(Purchase.VEHICLE_TYPE_CHOICES).items()}
                    vehicle_type_codes = []
                    for v in values:
                        if v in vehicle_type_map:
                            vehicle_type_codes.append(vehicle_type_map[v])
                        else:
                            vehicle_type_codes.append(v)
                    
                    if vehicle_type_codes:
                        if filter_type == 'include':
                            filter_conditions &= Q(vehicle_type__in=vehicle_type_codes)
                        else:
                            filter_conditions &= ~Q(vehicle_type__in=vehicle_type_codes)
                
                elif filter_column_id in ['factor_code', 'send_cottage_sms', 'is_weight_costed', 
                                        'is_ap_af', 'is_fully_tasvied', 'ready_for_invoice']:
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
                
                elif filter_column_id in ['total_weight', 'extelaf_weight', 'extelaf_amount',
                                         'purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit']:
                    numeric_values = []
                    for v in values:
                        try:
                            clean_value = str(v).replace(',', '').strip()
                            if clean_value:
                                numeric_values.append(float(clean_value))
                        except (ValueError, TypeError):
                            continue
                    
                    if numeric_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{filter_column_id}__in': numeric_values})
                        else:
                            filter_conditions &= ~Q(**{f'{filter_column_id}__in': numeric_values})
            
            # اعمال فیلترها
            if filter_conditions:
                queryset = queryset.filter(filter_conditions)
        
        # استخراج مقادیر بر اساس نوع ستون
        values = set()
        
        if column_id == 'purchase_number':
            values_queryset = queryset.exclude(purchase_number__isnull=True)\
                .exclude(purchase_number='').values_list('purchase_number', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'customer':
            values_queryset = queryset.exclude(customer__isnull=True)\
                .values_list('customer__name', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'invoice_id':
            values_queryset = queryset.exclude(invoice_id__isnull=True)\
                .exclude(invoice_id='').values_list('invoice_id', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'sales_agent':
            values_queryset = queryset.exclude(unique_sales_agent__isnull=True)\
                .values_list('unique_sales_agent__name', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'cargo':
            values_queryset = queryset.exclude(cargo__isnull=True)\
                .values_list('cargo__cottage', flat=True).distinct()
            values = set(values_queryset)
            
        elif column_id == 'status':
            values_queryset = queryset.values_list('state', flat=True).distinct()
            # تبدیل کدهای وضعیت به نمایش فارسی
            status_choices = dict(Purchase.STATUS_CHOICES)
            values = set([status_choices.get(state, state) for state in values_queryset if state])
            
        elif column_id in ['is_factored', 'is_urgent', 'is_canceled', 'is_archived']:
            # برای فیلدهای boolean، فقط مقادیری که واقعاً در دیتابیس وجود دارند را برگردان
            field_values = queryset.values_list(column_id, flat=True).distinct()
            values = set()
            for val in field_values:
                if val is True:
                    values.add('بله')
                elif val is False:
                    values.add('خیر')
            
        elif column_id in ['weight', 'delivered_weight', 'company_price', 'customer_price', 'amount_paid']:
            # بررسی دسترسی برای فیلدهای حساس
            if column_id in ['company_price', 'amount_paid'] and user_role in ['sales_agent', 'support_agent']:
                values = set()  # عدم دسترسی
            else:
                field_mapping = {
                    'weight': 'order_weight',
                    'delivered_weight': 'delivered_weight',
                    'company_price': 'company_price',
                    'customer_price': 'customer_price',
                    'amount_paid': 'amount_paid'
                }
                
                field_name = field_mapping.get(column_id, column_id)
                values_queryset = queryset.exclude(**{f'{field_name}__isnull': True})\
                    .exclude(**{field_name: 0})\
                    .values_list(field_name, flat=True).distinct()
                
                # فرمت اعداد با کاما - فقط مقادیر غیر صفر
                values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
            
        elif column_id == 'date':
            values_queryset = queryset.exclude(created_at__isnull=True)\
                .values_list('created_at__date', flat=True).distinct()
            # فرمت تاریخ
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])
            
        elif column_id == 'buyer_name':
            values_queryset = queryset.exclude(buyer_name__isnull=True)\
                .exclude(buyer_name='').values_list('buyer_name', flat=True).distinct()
            values = set(values_queryset)
        
        # ستون‌های جدید
        elif column_id == 'importer':
            values_queryset = queryset.exclude(cargo__vared_konandeh__isnull=True)\
                .values_list('cargo__vared_konandeh__name', flat=True).distinct()
            values = set(values_queryset)
        
        elif column_id == 'barbary':
            values_queryset = queryset.exclude(cargo__barbary__isnull=True)\
                .values_list('cargo__barbary__name', flat=True).distinct()
            values = set(values_queryset)
        
        elif column_id == 'barbary_phone':
            values_queryset = queryset.exclude(cargo__barbary__phone_number__isnull=True)\
                .exclude(cargo__barbary__phone_number='')\
                .values_list('cargo__barbary__phone_number', flat=True).distinct()
            values = set(values_queryset)
        
        elif column_id == 'product_type':
            values_queryset = queryset.exclude(cargo__product_type__isnull=True)\
                .values_list('cargo__product_type', flat=True).distinct()
            # تبدیل کدهای نوع محصول به نمایش فارسی
            from core.CargoProductModel import CargoProduct
            product_choices = dict(CargoProduct.PRODUCT_TYPES)
            values = set([product_choices.get(product_type, product_type) for product_type in values_queryset if product_type])
        
        
        elif column_id == 'first_barnameh_date':
            values_queryset = queryset.prefetch_related('barnamehs')\
                .exclude(barnamehs__isnull=True)\
                .exclude(barnamehs__barnameh_date__isnull=True)\
                .values_list('barnamehs__barnameh_date', flat=True).distinct()
            # فرمت تاریخ
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])
        
        elif column_id == 'last_barnameh_date':
            values_queryset = queryset.prefetch_related('barnamehs')\
                .exclude(barnamehs__isnull=True)\
                .exclude(barnamehs__barnameh_date__isnull=True)\
                .values_list('barnamehs__barnameh_date', flat=True).distinct()
            # فرمت تاریخ
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])
        
        elif column_id in ['address', 'description', 'unique_buyer_id', 'code_melli_tahvil', 
                          'bazaargah_phone_number', 'tahvil_phone_number', 'priority_reason',
                          'barbary_confidential_number', 'barbary_customer_number', 'delivery_receiver_name',
                          'buyer_national_id', 'unique_delivery_id', 'delivery_address', 'delivery_postal_code', 'factor_status']:
            values_queryset = queryset.exclude(**{f'{column_id}__isnull': True})\
                .exclude(**{f'{column_id}': ''}).values_list(column_id, flat=True).distinct()
            values = set(values_queryset)
        
        elif column_id in ['factor_code', 'send_cottage_sms', 'is_weight_costed', 
                          'is_ap_af', 'is_fully_tasvied']:
            field_values = queryset.values_list(column_id, flat=True).distinct()
            values = set()
            for val in field_values:
                if val is True:
                    values.add('بله')
                elif val is False:
                    values.add('خیر')
        
        elif column_id in ['total_weight', 'extelaf_weight', 'extelaf_amount']:
            values_queryset = queryset.exclude(**{f'{column_id}__isnull': True})\
                .exclude(**{column_id: 0})\
                .values_list(column_id, flat=True).distinct()
            values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
        
        elif column_id in ['type', 'payment_method', 'extelaf_type']:
            values_queryset = queryset.exclude(**{f'{column_id}__isnull': True})\
                .values_list(column_id, flat=True).distinct()
            values = set(values_queryset)
        
        elif column_id == 'priority':
            values_queryset = queryset.values_list('priority', flat=True).distinct()
            # تبدیل کدهای اولویت به نمایش فارسی
            priority_choices = dict(Purchase.PRIORITY_CHOICES)
            values = set([priority_choices.get(priority, priority) for priority in values_queryset if priority])
        
        elif column_id == 'buyer_user_type':
            values_queryset = queryset.exclude(buyer_user_type__isnull=True)\
                .values_list('buyer_user_type', flat=True).distinct()
            # تبدیل کدهای نوع کاربری به نمایش فارسی
            from core.CustomerModel import FIELD_OF_ACTIVITY
            user_type_choices = dict(FIELD_OF_ACTIVITY)
            values = set([user_type_choices.get(user_type, user_type) for user_type in values_queryset if user_type])
        
        elif column_id == 'vehicle_type':
            values_queryset = queryset.exclude(vehicle_type__isnull=True)\
                .values_list('vehicle_type', flat=True).distinct()
            # تبدیل کدهای نوع خودرو به نمایش فارسی
            from core.PurchaseModel import Purchase
            vehicle_choices = dict(Purchase.VEHICLE_TYPE_CHOICES)
            values = set([vehicle_choices.get(vehicle_type, vehicle_type) for vehicle_type in values_queryset if vehicle_type])
        
        elif column_id == 'shenase_takhsis':
            # استخراج شناسه‌های تخصیص از related objects
            shenase_codes = []
            for purchase in queryset.prefetch_related('shenase_takhsis_set'):
                codes = [s.code for s in purchase.shenase_takhsis_set.all()]
                shenase_codes.extend(codes)
            values = set(shenase_codes)
        
        elif column_id == 'updated_at':
            values_queryset = queryset.exclude(updated_at__isnull=True)\
                .values_list('updated_at__date', flat=True).distinct()
            values = set([date.strftime("%Y/%m/%d") for date in values_queryset if date])
        
        # فیلدهای مالی جدید
        elif column_id == 'ready_for_invoice':
            # فیلد boolean - آماده فاکتور
            field_values = queryset.values_list('ready_for_invoice', flat=True).distinct()
            values = set()
            for val in field_values:
                if val is True:
                    values.add('بله')
                elif val is False:
                    values.add('خیر')
        
        elif column_id in ['purchase_mabna_invoice', 'sales_mabna_invoice', 'mabna_profit']:
            # فیلدهای عددی - فاکتور خرید، فروش و سود
            # بررسی دسترسی برای فیلدهای حساس
            if user_role in ['sales_agent', 'support_agent']:
                values = set()  # عدم دسترسی
            else:
                values_queryset = queryset.exclude(**{f'{column_id}__isnull': True})\
                    .exclude(**{column_id: 0})\
                    .values_list(column_id, flat=True).distinct()
                
                # فرمت اعداد با کاما - فقط مقادیر غیر صفر
                values = set([f"{int(value):,}" for value in values_queryset if value is not None and value > 0])
        
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
        
        # منطق جدید: همه مقادیری که از query برگشتند "موجود" هستند
        # پس باید تیک خورده باشند (selected=True)
        # چون این مقادیر در نتیجه فیلترهای دیگر موجودند
        
        # تبدیل مقادیر به فرمت مورد نیاز برای frontend
        formatted_values = []
        for value in values_list[:200]:  # محدود کردن برای کارایی
            formatted_values.append({
                'value': value,
                'selected': True,  # همه مقادیر موجود باید تیک خورده باشند
                'display': str(value)
            })
        
        # برای اطلاعات اضافی، تعداد مقادیر قبلاً انتخاب شده در فیلتر فعلی
        previously_selected_count = 0
        if column_id in current_filters and current_filters[column_id].get('values'):
            previously_selected_values = current_filters[column_id]['values']
            previously_selected_count = len(previously_selected_values)
        
        return JsonResponse({
            'status': 'success',
            'values': formatted_values,
            'column_id': column_id,
            'count': len(formatted_values),
            'section': section,
            'total_available': len(values_list),
            'selected_count': len(formatted_values),  # همه موجود = همه انتخاب شده
            'previously_selected_count': previously_selected_count
        })
        
    except Exception as e:
        import traceback
        print(f"Error in get_purchase_column_values: {str(e)} , {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': "error"
        }, status=500)  