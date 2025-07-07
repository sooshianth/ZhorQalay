from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase
from django.db.models import Q
from openpyxl import Workbook
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
import json
from django.utils import timezone
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
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
import logging

logger = logging.getLogger("erp_purchase_list_view")

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
        'amount_paid', 'factor_code', 'unique_sales_agent'
    ]
    
    # فیلدهای customer و cargo
    customer_fields = ['customer__id', 'customer__name']
    cargo_fields = ['cargo__id', 'cargo__cottage']
    
    all_fields = selected_fields + customer_fields + cargo_fields
    
    # ایجاد QuerySet پایه
    base_queryset = Purchase.objects.only(*all_fields)\
        .select_related('customer', 'cargo', 'unique_sales_agent')\
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
            Q(tracking_number__icontains=global_search) |
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
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            # نام محصول
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
            # تلفن های مشتری
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            # نام تحویل گیرنده
            # تلفن خریدار
            {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'field': 'tahvil_phone_number'},        
        ]

        # todo: add the rest of the columns
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight', 'delivered_weight',
         'status', 'cargo', 'customer', 'buyer_name', 'tahvil_phone_number'] # نام محصول، تلفن های مشتری، تلفن خریدار، نام تحویل گیرنده
        
                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight',
             'delivered_weight', 'status', 'cargo', 'customer', 'buyer_name'] # تلفن های مشتری،  نام محصول
            logger.info("Using default columns for sales agent")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight',
                 'delivered_weight', 'status', 'cargo', 'customer', 'buyer_name'] # تلفن های مشتری،  نام محصول
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

    if user_role == 'support_agent':
        all_columns = [
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            # کارشناس فروش
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            # نام محصول
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'barbary', 'name': 'نام باربری', 'field': 'cargo.barbary.name'},
            # شماره باربری محرمانهی
            # شماره باربری مشتری
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            # نام تحویل گیرنده

        ]

        # todo: add the rest of the columns
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight',
         'delivered_weight', 'status', 'cargo', 'importer', 'barbary', 'customer',
          'buyer_name'] # کارشناس فروش، نام محصول، شماره باربری محرمانهی، شماره باربری مشتری، نام تحویل گیرنده
                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight', 
            'delivered_weight', 'status', 'cargo', 'importer' , 'customer', 'buyer_name'] # نام محصول، کارشناس فروش
            logger.info("Using default columns for support agent")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'weight',
                 'delivered_weight', 'status', 'cargo', 'importer' , 'customer', 'buyer_name'] # نام محصول، کارشناس فروش
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
    if user_role == 'financial_manager':
        all_columns = [
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            # کارشناس فروش
            {'id': 'company_price', 'name': 'فی خرید', 'field': 'company_price', 'unit': 'ریال'},
            {'id': 'customer_price', 'name': 'فی فروش', 'field': 'customer_price', 'unit': 'ریال'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            # تاریخ اولین بارنامه
            #تاریخ اخرین بارنامه 
            {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'field': 'extelaf_type'},
            {'id': 'extelaf_weight', 'name': 'وزن اختلاف', 'field': 'extelaf_weight', 'unit': 'کیلوگرم'},
            {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف', 'field': 'extelaf_amount', 'unit': 'ریال'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'description', 'name': 'توضیحات', 'field': 'description'},
            {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'field': 'is_fully_tasvied'},
            # اماده فاکتور
            # صدور فاکتور
            # فاکتور خرید مبنا
            # فاکتور فروش مبنا
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            # نام محصول
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            # نام تحویل گیرنده
            # شناسه ملی خریدار
            # ادرس خریدار
            # شناسه یکتا خریدار
        ]

        # todo: add the rest of the columns
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'company_price', 'customer_price', 'weight',
         'delivered_weight', 'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'status', 'description', 'is_fully_tasvied',
          'cargo', 'importer', 'buyer_name'] # کارشناس فروش، تاریخ اولین بارنامه، تاریخ اخرین بارنامه، اماده فاکتور، صدور فاکتور، فاکتور خرید مبنا، فاکتور فروش مبنا، نام محصول، 
          # نام تحویل گیرنده، شناسه ملی خریدار، ادرس خریدار، شناسه یکتا خریدار
                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'company_price', 'customer_price', 'weight',
             'delivered_weight', 'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'status', 'description', 'is_fully_tasvied',
             'cargo', 'importer', 'buyer_name'] # کارشناس فروش، اماده فاکتور، صدور فاکتور، فاکتور خرید مبنا، فاکتور فروش مبنا، نام محصول، 
             #  شناسه ملی خریدار، ادرس خریدار، شناسه یکتا خریدار
            logger.info("Using default columns for financial manager")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'company_price', 'customer_price', 'weight',
                 'delivered_weight', 'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'status', 'description', 'is_fully_tasvied',
                 'cargo', 'importer', 'buyer_name'] # کارشناس فروش، اماده فاکتور، صدور فاکتور، فاکتور خرید مبنا، فاکتور فروش مبنا، نام محصول، 
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

    if user_role == 'admin':
        all_columns = [
            {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number'},
            {'id': 'shenase_takhsis', 'name': 'شماره تخصیص', 'field': 'shenase_takhsis_set'},
            {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
            # کارشناس فروش
            {'id': 'company_price', 'name': 'فی خرید', 'field': 'company_price', 'unit': 'ریال'},
            {'id': 'customer_price', 'name': 'فی فروش', 'field': 'customer_price', 'unit': 'ریال'},
            {'id': 'weight', 'name': 'وزن خرید', 'field': 'order_weight', 'unit': 'کیلوگرم'},
            {'id': 'delivered_weight', 'name': 'وزن بارنامه شده', 'field': 'delivered_weight', 'unit': 'کیلوگرم'},
            # تاریخ اولین بارنامه
            #تاریخ اخرین بارنامه 
            {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'field': 'extelaf_type'},
            {'id': 'extelaf_weight', 'name': 'وزن اختلاف', 'field': 'extelaf_weight', 'unit': 'کیلوگرم'},
            {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف', 'field': 'extelaf_amount', 'unit': 'ریال'},
            {'id': 'status', 'name': 'وضعیت', 'field': 'state'},
            {'id': 'description', 'name': 'توضیحات', 'field': 'description'},
            {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'field': 'is_fully_tasvied'},
            # اماده فاکتور
            # صدور فاکتور
            # فاکتور خرید مبنا
            # فاکتور فروش مبنا
            # سود مبنا
            {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage'},
            # نام محصول
            {'id': 'importer', 'name': 'واردکننده', 'field': 'cargo.vared_konandeh.name'},
            {'id': 'barbary', 'name': 'نام باربری', 'field': 'cargo.barbary.name'},
            # شماره باربری محرمانهی
            # شماره باربری مشتری
            {'id': 'customer', 'name': 'نام مشتری', 'field': 'customer.name'},
            # تلفن های مشتری
            {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name'},
            # نام تحویل گیرنده
            # تلفن خریدار
            {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'field': 'tahvil_phone_number'},    
            # شناسه ملی خریدار
            # ادرس خریدار
            # شناسه یکتا خریدار
            # نوع کاربری خریدار
            # شناسه یکتای تحویل
            # ادرس تحویل
            # کد پستی تحویل
            {'id': 'code_melli_tahvil', 'name': 'کد ملی تحویل', 'field': 'code_melli_tahvil'},
            # تریلی
            # تک 
            # جفت
        ]

        # todo: add the rest of the columns
        allowed_columns = ['purchase_number', 'shenase_takhsis', 'date', 'company_price', 'customer_price', 'weight',
         'delivered_weight', 'extelaf_type', 'extelaf_weight', 'extelaf_amount', 'status', 'description', 'is_fully_tasvied',
          'cargo', 'importer', 'barbary', 'customer', 'buyer_name', 'tahvil_phone_number', 'code_melli_tahvil']
         # کارشناس فروش، تاریخ اولین بارنامه، تاریخ اخرین بارنامه، اماده فاکتور، صدور فاکتور، فاکتور خرید مبنا، فاکتور فروش مبنا، سود مبنا، نام محصول، 
          # نام تحویل گیرنده، شناسه ملی خریدار، ادرس خریدار، شناسه یکتا خریدار، نوع کاربری خریدار، شناسه یکتای تحویل، ادرس تحویل، کد پستی تحویل، تریلی، تک، جفت
          # شماره باربری محرمانهی، شماره باربری مشتری، تلفن خریدار، تلفن های مشتری

                
        # دریافت ستون های انتخاب شده از کوکی فقط برای کاربران محدود
        selected_columns = request.COOKIES.get('selected_columns', '')
        
        if not selected_columns:
            # پیش‌فرض برای کاربران محدود: نمایش همه ستون‌های مجاز
            #todo: add the rest of the columns
            selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'company_price', 'customer_price', 'weight',
            'delivered_weight', 'status', 'description', 'is_fully_tasvied',
            'cargo', 'importer', 'buyer_name', 'tahvil_phone_number', 'code_melli_tahvil']
             # کارشناس فروش، اماده فاکتور، صدور فاکتور، فاکتور خرید مبنا، فاکتور فروش مبنا، سود مبنا، نام محصول، 
             # تلفن خریدار
            logger.info("Using default columns for admin")
        else:
            # Make sure we have a string before splitting
            if isinstance(selected_columns, str):
                selected_columns = selected_columns.split(',')
            else:
                selected_columns = ['purchase_number', 'shenase_takhsis', 'date', 'company_price', 'customer_price', 'weight',
                'delivered_weight', 'status', 'description', 'is_fully_tasvied',
                'cargo', 'importer', 'buyer_name', 'tahvil_phone_number', 'code_melli_tahvil']
                # کارشناس فروش، اماده فاکتور، صدور فاکتور، فاکتور خرید مبنا، فاکتور فروش مبنا، سود مبنا، نام محصول، 
                # تلفن خریدار
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
    logger.warning(f"خرید های ارشیو شده توسط {request.user.username} لود شد. {get_client_ip(request)}")
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
        logger.warning(f"خطا در update_columns: {str(e)}, {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def export_to_excel(request):
    print("=== EXPORT TO EXCEL CALLED ===")
    print(f"Request method: {request.method}")
    logger.warning(f"خروجی اکسل توسط {request.user.username} با متد {request.method} و آی‌پی {get_client_ip(request)} آغاز شد")
    # Support both GET and POST requests
    if request.method == 'POST':
        purchase_ids = request.POST.get('ids', '').split(',')
        selected_columns = request.POST.get('columns', '')
    else:
        purchase_ids = request.GET.get('ids', '').split(',')
        selected_columns = request.GET.get('columns', '')
    logger.warning(f"raw select columns for user {request.user.username}: {selected_columns}")
    print(f"Raw purchase_ids: {purchase_ids}")
    print(f"Raw selected_columns: '{selected_columns}'")
    
    if selected_columns:
        # حذف کوتیشن‌های اضافی و decode کردن کاراکترهای escape شده
        selected_columns = selected_columns.strip('"').replace('\\054', ',').replace('\\\\', '\\')
        selected_columns = selected_columns.split(',')
        # حذف actions از لیست ستون‌ها چون در اکسل نمی‌خواهیم
        selected_columns = [col.strip() for col in selected_columns if col.strip() and col.strip() != 'actions']
    else:
        selected_columns = ['date', 'customer', 'invoice_id', 'sales_agent', 'purchase_number', 'weight', 'cargo', 'status']
    
    
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
    
    # تنظیم گردش متن از راست به چپ برای کل صفحه
    ws.sheet_view.rightToLeft = True
    
    # تعریف استایل‌ها
    header_font = Font(name='B Nazanin', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')
    
    # تنظیم راست چین و وسط چین
    alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
    
    # تعریف خطوط جدول
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # مپینگ کامل ستون‌ها به فیلدهای مدل - پشتیبانی از همه فیلدها
    column_mapping = {
        'purchase_number': ('شماره خرید', lambda p: p.purchase_number or "تعیین نشده"),
        'date': ('تاریخ', lambda p: p.created_at.strftime("%Y/%m/%d") if p.created_at else "-"),
        'customer': ('نام مشتری', lambda p: p.customer.name if p.customer else "نامشخص"),
        'invoice_id': ('کد درون سازمانی', lambda p: p.invoice_id or "تعیین نشده"),
        'sales_agent': ('نماینده فروش', lambda p: p.unique_sales_agent.name if p.unique_sales_agent else (", ".join([agent.name for agent in p.customer.sales_agent.all()]) if p.customer and p.customer.sales_agent.exists() else "-")),
        'weight': ('وزن (کیلوگرم)', lambda p: f"{p.order_weight:,}" if p.order_weight else "0"),
        'cargo': ('کوتاژ', lambda p: p.cargo.cottage if p.cargo and hasattr(p.cargo, 'cottage') else "-"),
        'importer': ('واردکننده', lambda p: p.cargo.vared_konandeh.name if p.cargo and hasattr(p.cargo, 'vared_konandeh') and p.cargo.vared_konandeh else "-"),
        'status': ('وضعیت', lambda p: dict(Purchase.STATUS_CHOICES).get(p.state, p.state) if p.state else "-"),
        'address': ('آدرس', lambda p: p.address or "-"),
        'description': ('توضیحات', lambda p: p.description or "-"),
        'factor_code': ('فاکتور مبنا', lambda p: "بله" if p.factor_code else "خیر"),
        'tracking_number': ('شماره پیگیری', lambda p: p.tracking_number or "-"),
        'shenase_takhsis': ('شناسه‌های تخصیص', lambda p: ", ".join([st.code for st in p.shenase_takhsis_set.all()]) if hasattr(p, 'shenase_takhsis_set') and p.shenase_takhsis_set.exists() else "-"),
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
        'priority': ('اولویت', lambda p: dict(Purchase.PRIORITY_CHOICES).get(p.priority, p.priority) if p.priority else "-"),
        'priority_reason': ('دلیل اولویت', lambda p: p.priority_reason or "-"),
        'barbary': ('نام باربری', lambda p: p.cargo.barbary.name if p.cargo and hasattr(p.cargo, 'barbary') and p.cargo.barbary else "-"),
        'company_price': ('فی خرید (ریال)', lambda p: f"{p.company_price:,}" if p.company_price else "0"),
        'customer_price': ('فی فروش (ریال)', lambda p: f"{p.customer_price:,}" if p.customer_price else "0"),
        'amount_paid': ('مبلغ پرداختی (ریال)', lambda p: f"{p.amount_paid:,}" if p.amount_paid else "0"),
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
    logger.warning(f"کاربر {request.user.username} درخواست دریافت لیست کوتاژ کرد. {get_client_ip(request)}")
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
    logger.warning(f"دریافت جزئیات کوتاز توسط {request.user.username} با آیپی {get_client_ip(request)}")
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
    logger.warning(f"ویرایش گروهی کوتاژ توسط {request.user.username} با ایپی {get_client_ip(request)}")
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
@role_required('admin', 'logistics_manager', 'financial_manager')
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
        
        # ذخیره در کوکی (به مدت 30 روز)
        response = JsonResponse({'status': 'success'})
        response.set_cookie('purchase_list_column_order', json.dumps(column_order), max_age=30*24*60*60)
        
        return response
    except Exception as e:
        logger.error(f"error update column: {str(e)}")
        return JsonResponse({'status': 'error', 'message': "error"}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager')
def reset_column_order(request):
    """
    بازگرداندن ترتیب ستون‌ها به حالت پیش‌فرض
    """
    logger.warning(f"بازگرداندن ترتیب جدید ستون ها توسط {request.user.username} و آیپی {get_client_ip(request)}")
    
    try:
        # ستون‌های پیش‌فرض اصلی
        default_columns = ['purchase_number', 'date', 'customer', 'invoice_id', 'sales_agent', 'weight', 'cargo', 'status', 'actions']
        
        # برای آسان‌تر کردن دیباگ
        print("Resetting column order to default:", default_columns)
        
        # ایجاد پاسخ
        response = JsonResponse({'success': True, 'message': 'ترتیب ستون‌ها به حالت پیش‌فرض بازگردانده شد'})
        
        # حذف تمامی کوکی‌های مربوط به ستون‌ها
        response.delete_cookie('purchase_list_column_order')
        response.delete_cookie('selected_columns')
        
        # تنظیم مجدد کوکی‌ها با مقادیر پیش‌فرض
        response.set_cookie('selected_columns', ','.join(default_columns))
        
        return response
    except Exception as e:
        logger.error(f"Error in reset_column_order: {str(e)}")
        return JsonResponse({'success': False, 'error': "error"}, status=500)

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
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
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
                Q(tracking_number__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |
                
                # توضیحات و اطلاعات اضافی
                Q(description__icontains=global_search) |
                Q(priority_reason__icontains=global_search) |
                
                # نماینده فروش
                Q(unique_sales_agent__name__icontains=global_search)
            )
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