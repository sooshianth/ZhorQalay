from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from datetime import datetime
import json
from core._models import Purchase
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .managers_profile_view import get_client_ip
import logging

logger = logging.getLogger("erp_purchase_filter_api")


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def get_purchase_table_configuration(request):
    """
    API برای دریافت تنظیمات ستون‌های جدول خریدها
    """
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
    try:
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        logger.warning(f"فیلتر ها: {filters}")
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
            'amount_paid', 'factor_code', 'buyer_name'
        ]
        
        # فیلدهای customer و cargo
        customer_fields = ['customer__id', 'customer__name']
        cargo_fields = ['cargo__id', 'cargo__cottage']
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
                
                elif column_id in ['address', 'description', 'tracking_number', 'code_melli_tahvil', 
                                 'bazaargah_phone_number', 'tahvil_phone_number', 'priority_reason']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': values})
                
                elif column_id in ['factor_code', 'send_cottage_sms', 'is_weight_costed', 
                                 'is_ap_af', 'is_fully_tasvied']:
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
                
                elif column_id in ['total_weight', 'extelaf_weight', 'extelaf_amount']:
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
                
                # اطلاعات ردیابی
                Q(tracking_number__icontains=global_search) |
                Q(shenase_takhsis_set__code__icontains=global_search) |
                
                # توضیحات و اطلاعات اضافی
                Q(description__icontains=global_search) |
                Q(priority_reason__icontains=global_search) |
                
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
                'tracking_number': 'tracking_number',
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
                'details': 'id',  # مرتب‌سازی بر اساس ID
                'جزئیات': 'id',  # مرتب‌سازی بر اساس ID
                'actions': 'id',  # مرتب‌سازی بر اساس ID
                'عملیات': 'id',  # مرتب‌سازی بر اساس ID
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
                'tracking_number': purchase.tracking_number or '-',
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
                    'raw_company_price': purchase.company_price or 0,
                    'raw_customer_price': purchase.customer_price or 0,
                    'raw_amount_paid': purchase.amount_paid or 0,
                })
            else:
                data.update({
                    'customer_price': f"{purchase.customer_price:,}" if purchase.customer_price else '0',
                    'raw_customer_price': purchase.customer_price or 0,
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
                
                elif filter_column_id in ['address', 'description', 'tracking_number', 
                                        'code_melli_tahvil', 'bazaargah_phone_number', 
                                        'tahvil_phone_number', 'priority_reason']:
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{filter_column_id}__in': values})
                        else:
                            filter_conditions &= ~Q(**{f'{filter_column_id}__in': values})
                
                elif filter_column_id in ['factor_code', 'send_cottage_sms', 'is_weight_costed', 
                                        'is_ap_af', 'is_fully_tasvied']:
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
                
                elif filter_column_id in ['total_weight', 'extelaf_weight', 'extelaf_amount']:
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
        
        elif column_id in ['address', 'description', 'tracking_number', 'code_melli_tahvil', 
                          'bazaargah_phone_number', 'tahvil_phone_number', 'priority_reason']:
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
        print(f"Error in get_purchase_column_values: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500) 