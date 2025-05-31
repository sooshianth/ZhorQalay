from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase, PurchaseEditLog
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

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def purchase_list(request):
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
    
    # پارامترهای فیلتر اضافی
    factor_code = request.GET.get('factor_code', '')
    is_urgent = request.GET.get('is_urgent', '')
    is_canceled = request.GET.get('is_canceled', '')
    is_fully_tasvied = request.GET.get('is_fully_tasvied', '')
    type = request.GET.get('type', '')
    payment_method = request.GET.get('payment_method', '')
    extelaf_type = request.GET.get('extelaf_type', '')
    send_cottage_sms = request.GET.get('send_cottage_sms', '')
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # فیلتر پایه: خریدهای آرشیو نشده و آرشیو شده
    active_purchases = Purchase.objects.exclude(state='ARCHIVED').exclude(is_archived=True).order_by('-created_at')
    archived_purchases = Purchase.objects.filter(Q(state='ARCHIVED') | Q(is_archived=True)).order_by('-created_at')

    # اگر کاربر کارشناس فروش است ولی نقش لجستیک ندارد، فقط خریدهای مشتریان خود را ببیند
    if user_role == 'sales_agent':
        active_purchases = active_purchases.filter(customer__sales_agent=request.user.sales_agent)
        archived_purchases = archived_purchases.filter(customer__sales_agent=request.user.sales_agent)

    # اگر فیلتر وضعیت آرشیو انتخاب شده است
    if is_archived != '':
        if is_archived == '1':
            active_purchases = Purchase.objects.none()  # لیست فعال خالی شود
        else:  # is_archived == '0'
            archived_purchases = Purchase.objects.none()  # لیست آرشیو خالی شود

    # اعمال فیلترهای پیشرفته
    if customer:
        active_purchases = active_purchases.filter(customer__name__icontains=customer)
        archived_purchases = archived_purchases.filter(customer__name__icontains=customer)
    
    if sales_agent:
        active_purchases = active_purchases.filter(customer__sales_agent__name__icontains=sales_agent)
        archived_purchases = archived_purchases.filter(customer__sales_agent__name__icontains=sales_agent)
    
    if invoice_id:
        active_purchases = active_purchases.filter(invoice_id__icontains=invoice_id)
        archived_purchases = archived_purchases.filter(invoice_id__icontains=invoice_id)
    
    if purchase_number:
        active_purchases = active_purchases.filter(purchase_number__icontains=purchase_number)
        archived_purchases = archived_purchases.filter(purchase_number__icontains=purchase_number)
    
    if cottage:
        active_purchases = active_purchases.filter(cargo__cottage__icontains=cottage)
        archived_purchases = archived_purchases.filter(cargo__cottage__icontains=cottage)
    
    if state:
        active_purchases = active_purchases.filter(state=state)
        archived_purchases = archived_purchases.filter(state=state)
    
    # فیلتر تاریخ
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            active_purchases = active_purchases.filter(created_at__date__gte=date_from_obj)
            archived_purchases = archived_purchases.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass  # تاریخ نامعتبر نادیده گرفته می‌شود
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            active_purchases = active_purchases.filter(created_at__date__lte=date_to_obj)
            archived_purchases = archived_purchases.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass  # تاریخ نامعتبر نادیده گرفته می‌شود
    
    # فیلتر وزن
    if min_weight:
        try:
            min_weight_float = float(min_weight)
            active_purchases = active_purchases.filter(order_weight__gte=min_weight_float)
            archived_purchases = archived_purchases.filter(order_weight__gte=min_weight_float)
        except ValueError:
            pass  # مقدار نامعتبر نادیده گرفته می‌شود
    
    if max_weight:
        try:
            max_weight_float = float(max_weight)
            active_purchases = active_purchases.filter(order_weight__lte=max_weight_float)
            archived_purchases = archived_purchases.filter(order_weight__lte=max_weight_float)
        except ValueError:
            pass  # مقدار نامعتبر نادیده گرفته می‌شود
    
    # فیلتر نوع محصول و کشور
    if product_type:
        active_purchases = active_purchases.filter(cargo__product_type=product_type)
        archived_purchases = archived_purchases.filter(cargo__product_type=product_type)
    
    if country:
        active_purchases = active_purchases.filter(cargo__country=country)
        archived_purchases = archived_purchases.filter(cargo__country=country)
    
    # فیلتر وضعیت فاکتور
    if is_factored != '':
        is_factored_bool = is_factored == '1'
        active_purchases = active_purchases.filter(is_factored=is_factored_bool)
        archived_purchases = archived_purchases.filter(is_factored=is_factored_bool)
    
    # فیلتر اولویت
    if priority:
        active_purchases = active_purchases.filter(priority=priority)
        archived_purchases = archived_purchases.filter(priority=priority)
    
    # فیلترهای اضافی
    if factor_code:
        active_purchases = active_purchases.filter(factor_code__icontains=factor_code)
        archived_purchases = archived_purchases.filter(factor_code__icontains=factor_code)
    
    if is_urgent == '1':
        active_purchases = active_purchases.filter(is_urgent=True)
        archived_purchases = archived_purchases.filter(is_urgent=True)
    
    if is_canceled == '1':
        active_purchases = active_purchases.filter(Q(is_canceled=True) | Q(state='CANCELED'))
        archived_purchases = archived_purchases.filter(Q(is_canceled=True) | Q(state='CANCELED'))
    
    if is_fully_tasvied == '1':
        active_purchases = active_purchases.filter(is_fully_tasvied=True)
        archived_purchases = archived_purchases.filter(is_fully_tasvied=True)
    
    if type:
        active_purchases = active_purchases.filter(type=type)
        archived_purchases = archived_purchases.filter(type=type)
    
    if payment_method:
        active_purchases = active_purchases.filter(payment_method=payment_method)
        archived_purchases = archived_purchases.filter(payment_method=payment_method)
    
    if extelaf_type:
        active_purchases = active_purchases.filter(extelaf_type=extelaf_type)
        archived_purchases = archived_purchases.filter(extelaf_type=extelaf_type)
    
    if send_cottage_sms != '':
        send_cottage_sms_bool = send_cottage_sms == '1'
        active_purchases = active_purchases.filter(send_cottage_sms=send_cottage_sms_bool)
        archived_purchases = archived_purchases.filter(send_cottage_sms=send_cottage_sms_bool)
    
    # اعمال فیلتر جستجوی سریع در آخر
    if global_search:
        active_purchases = active_purchases.filter(
            Q(customer__name__icontains=global_search) |
            Q(customer__sales_agent__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(order_weight__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__product_type__icontains=global_search) |
            Q(cargo__country__icontains=global_search) |
            Q(created_at__contains=global_search)
        )
        archived_purchases = archived_purchases.filter(
            Q(customer__name__icontains=global_search) |
            Q(customer__sales_agent__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(order_weight__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__product_type__icontains=global_search) |
            Q(cargo__country__icontains=global_search) |
            Q(created_at__contains=global_search)
        )
    
    # فهرست وضعیت‌ها برای فیلتر
    all_states = dict(Purchase.STATUS_CHOICES)

    # دریافت ستون های انتخاب شده از کوکی
    selected_columns = request.COOKIES.get('selected_columns', '')
    
    # For debugging
    print(f"Cookie selected_columns: '{selected_columns}'")
    
    if not selected_columns:
        selected_columns = 'purchase_number,date,customer,invoice_id,sales_agent,weight,cargo,status,actions'
        print("Using default columns")
    
    # Make sure we have a string before splitting
    if isinstance(selected_columns, str):
        selected_columns = selected_columns.split(',')
    else:
        selected_columns = ['purchase_number', 'date', 'customer', 'invoice_id', 'sales_agent', 'weight', 'cargo', 'status', 'actions']
        print("Type error on selected_columns - using defaults")
    
    # اطمینان از حضور ستون actions
    if 'actions' not in selected_columns:
        selected_columns.append('actions')
    
    print(f"Final selected columns: {selected_columns}")
    
    # تعریف ایندکس ستون ها برای نمایش/مخفی کردن آنها در جاوااسکریپت
    column_indices = {
        'purchase_number': 1,
        'date': 2,
        'customer': 3,
        'invoice_id': 4,
        'sales_agent': 5,
        'weight': 6,
        'cargo': 7,
        'status': 8,
        'actions': 9
    }
    
    # لیست همه ستون های ممکن با اطلاعات لازم
    all_columns = [
        {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number', 'editable': True},
        {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
        {'id': 'customer', 'name': 'مشتری', 'field': 'customer.name', 'editable': False},
        {'id': 'invoice_id', 'name': 'کد درون سازمانی', 'field': 'invoice_id', 'editable': True},
        {'id': 'sales_agent', 'name': 'نماینده فروش', 'field': 'customer.sales_agent.name', 'editable': False},
        {'id': 'weight', 'name': 'وزن (کیلوگرم)', 'field': 'order_weight', 'editable': True},
        {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage', 'editable': True},
        {'id': 'status', 'name': 'وضعیت‌ها', 'field': 'state', 'editable': True},
        {'id': 'actions', 'name': 'جزئیات', 'editable': False},
        # ستون‌های اضافی
        {'id': 'address', 'name': 'آدرس', 'field': 'address', 'editable': False},
        {'id': 'description', 'name': 'توضیحات', 'field': 'description', 'editable': False},
        {'id': 'company_price', 'name': 'فی خرید (ریال)', 'field': 'company_price', 'editable': False},
        {'id': 'customer_price', 'name': 'فی فروش (ریال)', 'field': 'customer_price', 'editable': False},
        {'id': 'factor_code', 'name': 'فاکتور کد', 'field': 'factor_code', 'editable': False},
        {'id': 'tracking_number', 'name': 'شماره پیگیری', 'field': 'tracking_number', 'editable': False},
        {'id': 'shenase_takhsis', 'name': 'شناسه تخصیص', 'field': 'shenase_takhsis', 'editable': False},
        {'id': 'code_melli_tahvil', 'name': 'کد ملی تحویل', 'field': 'code_melli_tahvil', 'editable': False},
        {'id': 'bazaargah_phone_number', 'name': 'شماره تلفن بازارگاه', 'field': 'bazaargah_phone_number', 'editable': False},
        {'id': 'buyer_name', 'name': 'نام خریدار', 'field': 'buyer_name', 'editable': False},
        {'id': 'tahvil_phone_number', 'name': 'شماره تلفن تحویل', 'field': 'tahvil_phone_number', 'editable': False},
        {'id': 'send_cottage_sms', 'name': 'ارسال پیامک کوتاژ', 'field': 'send_cottage_sms', 'editable': False},
        {'id': 'total_weight', 'name': 'وزن کل (کیلوگرم)', 'field': 'total_weight', 'editable': False},
        {'id': 'delivered_weight', 'name': 'وزن بارنامه شده (کیلوگرم)', 'field': 'delivered_weight', 'editable': False},
        {'id': 'type', 'name': 'نوع خرید', 'field': 'type', 'editable': False},
        {'id': 'amount_paid', 'name': 'مبلغ پرداختی (ریال)', 'field': 'amount_paid', 'editable': False},
        {'id': 'payment_method', 'name': 'شیوه پرداخت', 'field': 'payment_method', 'editable': False},
        {'id': 'updated_at', 'name': 'تاریخ بروزرسانی', 'field': 'updated_at', 'editable': False},
        {'id': 'is_weight_costed', 'name': 'کسر از وزن موجود', 'field': 'is_weight_costed', 'editable': False},
        {'id': 'is_ap_af', 'name': 'اتوکامپلیت شده', 'field': 'is_ap_af', 'editable': False},
        {'id': 'extelaf_type', 'name': 'نوع اختلاف', 'field': 'extelaf_type', 'editable': False},
        {'id': 'extelaf_weight', 'name': 'وزن اختلاف (کیلوگرم)', 'field': 'extelaf_weight', 'editable': False},
        {'id': 'extelaf_amount', 'name': 'مبلغ اختلاف (ریال)', 'field': 'extelaf_amount', 'editable': False},
        {'id': 'is_urgent', 'name': 'فوری', 'field': 'is_urgent', 'editable': False},
        {'id': 'is_canceled', 'name': 'لغو شده', 'field': 'is_canceled', 'editable': False},
        {'id': 'is_archived', 'name': 'آرشیو شده', 'field': 'is_archived', 'editable': False},
        {'id': 'is_fully_tasvied', 'name': 'تسویه کامل', 'field': 'is_fully_tasvied', 'editable': False},
        {'id': 'is_factored', 'name': 'ثبت فاکتور', 'field': 'is_factored', 'editable': False},
        {'id': 'priority', 'name': 'اولویت', 'field': 'priority', 'editable': False},
        {'id': 'priority_reason', 'name': 'دلیل اولویت', 'field': 'priority_reason', 'editable': False},
    ]

    context = {
        'active_purchases': active_purchases,
        'archived_purchases': archived_purchases,
        'all_states': all_states,
        'user_role': user_role,  # افزودن نقش کاربر به context
        # پارامترهای جستجو برای حفظ وضعیت در فرم
        'search_params': {
            'global_search': global_search,
            'customer': customer,
            'sales_agent': sales_agent,
            'invoice_id': invoice_id,
            'purchase_number': purchase_number,
            'cottage': cottage,
            'state': state,
            'date_from': date_from,
            'date_to': date_to,
            'min_weight': min_weight,
            'max_weight': max_weight,
            'product_type': product_type,
            'country': country,
            'is_archived': is_archived,
            'is_factored': is_factored,
            'priority': priority,
            'factor_code': factor_code,
            'is_urgent': is_urgent,
            'is_canceled': is_canceled,
            'is_fully_tasvied': is_fully_tasvied,
            'type': type,
            'payment_method': payment_method,
            'extelaf_type': extelaf_type,
            'send_cottage_sms': send_cottage_sms,
        },
        'selected_columns': selected_columns,
        'all_columns': all_columns,
        'column_mapping': {
            'purchase_number': 0,
            'date': 1,
            'customer': 2,
            'invoice_id': 3,
            'sales_agent': 4,
            'weight': 5,
            'cargo': 6,
            'status': 7,
            'actions': 8
        },
        'column_indices': json.dumps(column_indices),
        'actions_column_index': column_indices['actions']
    }
    
    return render(request, 'purchase_list.html', context)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
@login_required
def update_columns(request):
    """
    Actualiza las columnas seleccionadas para mostrar en la lista de compras
    """
    try:
        # Obtener las columnas seleccionadas del formulario
        selected_columns = request.POST.getlist('columns[]')
        
        # Registrar para depuración
        print(f"Columnas recibidas: {selected_columns}")
        print(f"Datos POST completos: {dict(request.POST)}")
        
        # Comprobar si hay datos en un formato alternativo
        if not selected_columns and 'columns' in request.POST:
            selected_columns = request.POST.getlist('columns')
            print(f"Usando formato alternativo: {selected_columns}")
        
        # Si todavía no hay columnas, buscar otro formato posible
        if not selected_columns and request.POST.get('columns'):
            # Intentar con una cadena separada por comas
            columns_str = request.POST.get('columns')
            selected_columns = [c.strip() for c in columns_str.split(',') if c.strip()]
            print(f"Usando cadena separada por comas: {selected_columns}")
        
        # Verificar que hay columnas seleccionadas
        if not selected_columns:
            return JsonResponse({
                'status': 'error', 
                'message': 'No se recibieron columnas seleccionadas'
            }, status=400)
        
        # Asegurar que la columna de acciones siempre está presente
        if 'actions' not in selected_columns:
            selected_columns.append('actions')  # ستون جزئیات همیشه باید نمایش داده شود
        
        # Crear la respuesta y establecer la cookie
        cookie_value = ','.join(selected_columns)
        print(f"Setting cookie 'selected_columns' with value: {cookie_value}")
        
        response = JsonResponse({'status': 'success', 'selected_columns': selected_columns})
        
        # Establecer la cookie con un período de validez de 30 días
        # Parámetro httponly=False para permitir acceso desde JavaScript
        # Asegurar valores correctos para SameSite y Secure
        response.set_cookie(
            'selected_columns', 
            cookie_value, 
            max_age=30*24*60*60,  # 30 días
            httponly=False,       # Permitir acceso desde JavaScript
            samesite='Lax'        # Permitir envío en contextos de navegación
        )
        
        return response
    except Exception as e:
        import traceback
        print(f"Error en update_columns: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def export_to_excel(request):
    purchase_ids = request.GET.get('ids', '').split(',')
    selected_columns = request.GET.get('columns', '')
    
    if selected_columns:
        selected_columns = selected_columns.split(',')
    else:
        selected_columns = ['date', 'customer', 'invoice_id', 'sales_agent', 'purchase_number', 'weight', 'cargo', 'status']
    
    # فیلتر کردن آیدی‌های خالی
    purchase_ids = [pid for pid in purchase_ids if pid]
    
    if not purchase_ids:
        return JsonResponse({'status': 'error', 'message': 'هیچ خریدی انتخاب نشده است'}, status=400)
    
    try:
        # برای عملکرد بهتر، اگر تعداد خریدهای انتخاب شده زیاد است، در تکه‌های کوچکتر پردازش کنیم
        purchases = Purchase.objects.filter(id__in=purchase_ids).select_related('customer', 'cargo').prefetch_related('customer__sales_agent').order_by('-created_at')
        
        wb = Workbook()
        ws = wb.active
        ws.title = "لیست خریدها"
        
        # تنظیم گردش متن از راست به چپ برای کل صفحه
        ws.sheet_view.rightToLeft = True
        
        # تعریف استایل‌ها
        header_font = Font(name='B Nazanin', size=12, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')  # رنگ سبز
        
        # استایل برای ردیف‌های زوج
        even_row_fill = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')  # سبز بسیار کمرنگ
        
        # تنظیم راست چین و وسط چین
        alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
        
        # تعریف خطوط جدول
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # مپینگ ستون‌ها به فیلدهای مدل با بهبود مدیریت خطا
        column_mapping = {
            'date': ('تاریخ', lambda p: p.created_at.strftime("%Y/%m/%d") if p.created_at else "-"),
            'customer': ('مشتری', lambda p: p.customer.name if p.customer else "نامشخص"),
            'invoice_id': ('کد درون سازمانی', lambda p: p.invoice_id or "تعیین نشده"),
            'sales_agent': ('نماینده فروش', lambda p: ", ".join([agent.name for agent in p.customer.sales_agent.all()]) if p.customer and p.customer.sales_agent.exists() else "-"),
            'purchase_number': ('شماره خرید', lambda p: p.purchase_number or "تعیین نشده"),
            'weight': ('وزن (کیلوگرم)', lambda p: f"{p.order_weight:,}" if p.order_weight else "0"),
            'cargo': ('کوتاژ', lambda p: p.cargo.cottage if p.cargo and hasattr(p.cargo, 'cottage') else "-"),
            'status': ('وضعیت', lambda p: dict(Purchase.STATUS_CHOICES).get(p.state, p.state) if p.state else "-"),
            'address': ('آدرس', lambda p: p.address or "-"),
            'description': ('توضیحات', lambda p: p.description or "-"),
            'company_price': ('فی خرید (ریال)', lambda p: f"{p.company_price:,}" if p.company_price else "0"),
            'customer_price': ('فی فروش (ریال)', lambda p: f"{p.customer_price:,}" if p.customer_price else "0"),
            'factor_code': ('فاکتور کد', lambda p: "بله" if p.factor_code else "خیر"),
            'tracking_number': ('شماره پیگیری', lambda p: p.tracking_number or "-"),
            'shenase_takhsis': ('شناسه تخصیص', lambda p: p.shenase_takhsis or "-"),
            'code_melli_tahvil': ('کد ملی تحویل', lambda p: p.code_melli_tahvil or "-"),
            'bazaargah_phone_number': ('شماره تلفن بازارگاه', lambda p: p.bazaargah_phone_number or "-"),
            'buyer_name': ('نام خریدار', lambda p: p.buyer_name or "-"),
            'tahvil_phone_number': ('شماره تلفن تحویل', lambda p: p.tahvil_phone_number or "-"),
            'send_cottage_sms': ('ارسال پیامک کوتاژ', lambda p: "بله" if p.send_cottage_sms else "خیر"),
            'total_weight': ('وزن کل (کیلوگرم)', lambda p: f"{p.total_weight:,}" if p.total_weight else "0"),
            'delivered_weight': ('وزن بارنامه شده (کیلوگرم)', lambda p: f"{p.delivered_weight:,}" if p.delivered_weight else "0"),
            'type': ('نوع خرید', lambda p: "بازارگاه" if p.type == "bazaargah" else "خارج از بازارگاه"),
            'amount_paid': ('مبلغ پرداختی (ریال)', lambda p: f"{p.amount_paid:,}" if p.amount_paid else "0"),
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
            'priority': ('اولویت', lambda p: dict(Purchase.PRIORITY_CHOICES).get(p.priority, "عادی") if p.priority else "عادی"),
            'priority_reason': ('دلیل اولویت', lambda p: p.priority_reason or "-"),
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
        batch_size = 100  # پردازش خریدها در گروه‌های 100 تایی برای کارایی بهتر
        row_idx = 2
        
        for i in range(0, len(purchases), batch_size):
            batch = purchases[i:i+batch_size]
            for purchase in batch:
                row = []
                for col in selected_columns:
                    if col in column_mapping:
                        try:
                            value = column_mapping[col][1](purchase)
                            row.append(value)
                        except Exception as e:
                            print(f"خطا در استخراج مقدار {col} برای خرید {purchase.id}: {str(e)}")
                            row.append("-")
                ws.append(row)
                
                # تنظیم استایل برای سطرهای داده
                for j, cell in enumerate(ws[row_idx], 1):
                    cell.alignment = alignment
                    cell.border = thin_border
                    
                    # استایل متناوب برای سطرها
                    if row_idx % 2 == 0:
                        cell.fill = even_row_fill
                
                row_idx += 1
        
        # تنظیم عرض ستون‌ها
        for i, column in enumerate(ws.columns, 1):
            max_length = 0
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = adjusted_width
        
        # اضافه کردن فریز به سطر هدر
        ws.freeze_panes = "A2"
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"purchases_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response
        
    except Exception as e:
        # لاگ خطا
        print(f"Error in export_to_excel: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد فایل اکسل: {str(e)}'}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def update_purchase_field(request):
    """
    API برای به‌روزرسانی فیلدهای قابل ویرایش خرید
    """
    try:
        purchase_id = request.POST.get('id')
        field_name = request.POST.get('field')
        value = request.POST.get('value')
        old_value = request.POST.get('old_value')
        
        # بررسی دسترسی‌ها
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            return JsonResponse({'status': 'error', 'message': 'شما دسترسی ویرایش ندارید'}, status=403)
        
        purchase = Purchase.objects.get(id=purchase_id)
        
        # ذخیره مقدار قدیمی برای لاگ
        if field_name == 'invoice_id':
            old_value_for_log = purchase.invoice_id
        elif field_name == 'purchase_number':
            old_value_for_log = purchase.purchase_number
        elif field_name == 'order_weight':
            old_value_for_log = str(purchase.order_weight) if purchase.order_weight is not None else ""
        elif field_name == 'state':
            old_value_for_log = purchase.state
        else:
            old_value_for_log = old_value or ""
            
        # تعیین فیلدهای مجاز برای ویرایش
        allowed_fields = {
            'invoice_id': lambda p, v: setattr(p, 'invoice_id', v),
            'purchase_number': lambda p, v: setattr(p, 'purchase_number', v),
            'order_weight': lambda p, v: setattr(p, 'order_weight', float(v) if v else None),
            'state': lambda p, v: setattr(p, 'state', v)
        }
        
        if field_name in allowed_fields:
            # ذخیره تغییرات
            allowed_fields[field_name](purchase, value)
            
            # اگر وضعیت فاکتور ارسال شده باشد، آن را نیز ذخیره کنیم
            is_factored = request.POST.get('is_factored')
            if is_factored is not None:
                is_factored_bool = is_factored.lower() == 'true'
                purchase.is_factored = is_factored_bool
                
                # اگر وضعیت صدور فاکتور است، همیشه بولین را true کنیم
                if field_name == 'state' and value == 'INVOICE_ISSUED':
                    purchase.is_factored = True
                
                # ثبت تغییر وضعیت فاکتور در لاگ
                log_entry_invoice = PurchaseEditLog(
                    purchase=purchase,
                    user=request.user,
                    field_name='is_factored',
                    old_value=str(purchase.is_factored),
                    new_value=str(is_factored_bool),
                    edit_time=timezone.now()
                )
                log_entry_invoice.save()
            
            purchase.save()
            
            # ثبت تغییرات در لاگ
            log_entry = PurchaseEditLog(
                purchase=purchase,
                user=request.user,
                field_name=field_name,
                old_value=old_value_for_log,
                new_value=value,
                edit_time=timezone.now()
            )
            log_entry.save()
            
            return JsonResponse({
                'status': 'success',
                'log_id': log_entry.id,  # برگرداندن شناسه لاگ برای استفاده احتمالی در بازگشت به نسخه قبلی
                'old_value': old_value_for_log
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'فیلد غیرمجاز'}, status=400)
    
    except Purchase.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'خرید یافت نشد'}, status=404)
    except ValueError as e:
        # خطای تبدیل داده (مثلاً وارد کردن حروف به جای عدد)
        return JsonResponse({'status': 'error', 'message': 'خطای تبدیل داده: لطفاً مقدار صحیح وارد کنید'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def revert_purchase_edit(request):
    """
    API برای بازگرداندن تغییرات یک فیلد به حالت قبلی
    """
    try:
        log_id = request.POST.get('log_id')
        
        if not log_id:
            return JsonResponse({'status': 'error', 'message': 'شناسه لاگ ارسال نشده است'}, status=400)
        
        # پیدا کردن لاگ مورد نظر
        log_entry = PurchaseEditLog.objects.get(id=log_id)
        purchase = log_entry.purchase
        
        # بررسی دسترسی‌ها
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            return JsonResponse({'status': 'error', 'message': 'شما دسترسی بازگرداندن تغییرات را ندارید'}, status=403)
        
        # بازگرداندن مقدار به حالت قبلی
        if log_entry.field_name == 'invoice_id':
            purchase.invoice_id = log_entry.old_value
        elif log_entry.field_name == 'purchase_number':
            purchase.purchase_number = log_entry.old_value
        elif log_entry.field_name == 'order_weight':
            try:
                purchase.order_weight = float(log_entry.old_value) if log_entry.old_value else None
            except ValueError:
                purchase.order_weight = None
        elif log_entry.field_name == 'state':
            purchase.state = log_entry.old_value
            
        purchase.save()
        
        # ثبت عملیات بازگرداندن در لاگ
        revert_log = PurchaseEditLog(
            purchase=purchase,
            user=request.user,
            field_name=log_entry.field_name,
            old_value=log_entry.new_value,  # مقدار جدید به قدیمی تبدیل می‌شود
            new_value=log_entry.old_value,  # مقدار قدیمی به جدید تبدیل می‌شود
            edit_time=timezone.now(),
            is_revert=True,
            reverted_log=log_entry
        )
        revert_log.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'تغییرات با موفقیت بازگردانده شد',
            'field_name': log_entry.field_name,
            'value': log_entry.old_value,
            'purchase_id': purchase.id
        })
        
    except PurchaseEditLog.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'لاگ مورد نظر یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def get_purchase_edit_logs(request, purchase_id):
    """
    دریافت تاریخچه تغییرات یک خرید
    """
    try:
        purchase = Purchase.objects.get(id=purchase_id)
        logs = PurchaseEditLog.objects.filter(purchase=purchase).order_by('-edit_time')
        
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'field_name': log.field_name,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'user': log.user.username,
                'edit_time': log.edit_time.strftime("%Y/%m/%d %H:%M:%S"),
                'is_revert': log.is_revert
            })
            
        return JsonResponse({'status': 'success', 'logs': logs_data})
    
    except Purchase.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'خرید مورد نظر یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def cargo_products_list(request):
    """
    API برای دریافت لیست کوتاژها
    """
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def cargo_product_details(request):
    """
    API برای دریافت جزئیات یک کوتاژ بر اساس شماره کوتاژ
    """
    try:
        cottage = request.GET.get('cottage', '')
        
        if not cottage:
            return JsonResponse({'status': 'error', 'message': 'شماره کوتاژ ارسال نشده است'}, status=400)
        
        try:
            cargo = CargoProduct.objects.get(cottage=cottage)
        except CargoProduct.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
        
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def bulk_edit_cargo(request):
    """
    API برای ویرایش گروهی کوتاژ
    """
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def reset_column_order(request):
    """
    بازگرداندن ترتیب ستون‌ها به حالت پیش‌فرض
    """
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
        print(f"Error in reset_column_order: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)