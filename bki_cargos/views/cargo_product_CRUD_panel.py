from django.shortcuts import render, redirect
from core._models import CargoProduct, VaredKonandeh, Barbary
from django.contrib.auth.decorators import login_required
from core.decorators.decorators import role_required
from django.http import JsonResponse
from django.db.models import Q
from django.db import connection
from core.decorators.det_user_role import determine_user_role
import logging

logger = logging.getLogger("bki_cargos_cargo_product_CRUD_panel")

def get_client_ip(request):
    """
    دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
    """
    if not request:
        return "Unknown"
        
    # IP مستقیم (از سرور دیده می‌شود)
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
    # IP از طریق proxy headers
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')

    # انتخاب IP اصلی
    client_ip = direct_ip
    if forwarded_for:
        # اولین IP در لیست X-Forwarded-For
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
        
    # اگر proxy وجود دارد، هر دو IP را نمایش بده
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
        
    return f"{client_ip}-{proxy_info}"

@role_required('admin', 'logistics_manager')
@login_required
def cargo_product_crud_panel(request, product_id=None):
    # اجازه ویرایش تکی محصولات داده نمی‌شود
    if product_id:
        return redirect('cargo_product_list')
    
    product = None
    if request.method == 'POST':
        data = request.POST
        # فقط ایجاد محصول جدید
        # Create new product
        vared_konandeh = None
        if data.get('vared_konandeh'):
            vared_konandeh = VaredKonandeh.objects.get(id=data.get('vared_konandeh'))
            
        barbary = None
        if data.get('barbary'):
            barbary = Barbary.objects.get(id=data.get('barbary'))
            
        CargoProduct.objects.create(
            type=data.get('type'),
            cottage=data.get('cottage'),
            company_price=data.get('company_price'),
            customer_price=data.get('customer_price'),
            product_type=data.get('product_type'),
            country=data.get('country'),
            vared_konandeh=vared_konandeh,
            barbary=barbary,
            port=data.get('port'),
            loading_time=data.get('loading_time'),
            description=data.get('description'),
            weight=data.get('weight'),
            status=data.get('status') == 'on'
        )
        return redirect('cargo_product_list')
    
    # Get all vared_konandeh and barbary for dropdown
    vared_konandehs = VaredKonandeh.objects.all()
    barbaries = Barbary.objects.all()
    
    return render(request, 'cargo_product_crud_panel.html', {
        'product': product, 
        'purchase_types': CargoProduct.PURCHASE_TYPES, 
        'product_types': CargoProduct.PRODUCT_TYPES, 
        'countries': CargoProduct.COUNTRIES, 
        'ports': CargoProduct.PORTS,
        'vared_konandehs': vared_konandehs,
        'barbaries': barbaries
    })

@role_required('admin', 'logistics_manager')
@login_required
def bulk_edit_cargo_products(request):
    logger.warning(f"ویرایش گروهی محصولات: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        # اگر از صفحه ویرایش گروهی آمده است
        if 'product_ids_str' in request.POST:
            product_ids_str = request.POST.get('product_ids_str', '')
            product_ids = [int(id_str) for id_str in product_ids_str.split(',') if id_str.isdigit()]
        # اگر از صفحه لیست آمده است
        else:
            product_ids_str = request.POST.get('product_ids', '')            
            # اگر فیلد product_ids به صورت رشته متنی با کاما باشد
            if product_ids_str:
                product_ids = [int(id_str) for id_str in product_ids_str.split(',') if id_str.isdigit()]
            else:
                # بازگشت به صفحه لیست اگر هیچ محصولی انتخاب نشده باشد
                return redirect('cargo_product_list')
        
        if not product_ids:
            # اگر هیچ آیدی معتبری نباشد، به صفحه لیست برگرد
            return redirect('cargo_product_list')
            
        products = CargoProduct.objects.filter(id__in=product_ids)
        
        if not products.exists():
            # اگر هیچ محصولی یافت نشد، به صفحه لیست برگرد
            return redirect('cargo_product_list')
            
        if request.POST.get('apply_changes') == 'true':
            # اعمال تغییرات
            
            # تغییر وضعیت
            if 'enable_status' in request.POST:
                status = request.POST.get('status') == 'on'
                products.update(status=status)
                
            # تغییر قیمت‌ها
            if 'enable_price' in request.POST:
                if request.POST.get('company_price'):
                    # استفاده از متد جدید برای به‌روزرسانی دقیق قیمت
                    company_price = int(request.POST.get('company_price'))
                    for product in products:
                        CargoProduct.update_exact_price(product.id, 'company_price', company_price)
                    
                if request.POST.get('customer_price'):
                    # استفاده از متد جدید برای به‌روزرسانی دقیق قیمت
                    customer_price = int(request.POST.get('customer_price'))
                    for product in products:
                        CargoProduct.update_exact_price(product.id, 'customer_price', customer_price)
            
            # تغییر کشور
            if 'enable_country' in request.POST:
                if request.POST.get('country'):
                    country = request.POST.get('country')
                    products.update(country=country)
            
            # تغییر نوع محصول
            if 'enable_product_type' in request.POST:
                if request.POST.get('product_type'):
                    product_type = request.POST.get('product_type')
                    products.update(product_type=product_type)
            
            # تغییر وارد کننده و باربری
            if 'enable_companies' in request.POST:
                if request.POST.get('vared_konandeh'):
                    vared_konandeh_id = int(request.POST.get('vared_konandeh'))
                    products.update(vared_konandeh_id=vared_konandeh_id)
                
                if request.POST.get('barbary'):
                    barbary_id = int(request.POST.get('barbary'))
                    products.update(barbary_id=barbary_id)
            
            # تغییر اطلاعات بارگیری
            if 'enable_loading' in request.POST:
                if request.POST.get('port'):
                    port = request.POST.get('port')
                    products.update(port=port)
                
                if request.POST.get('loading_time'):
                    loading_time = request.POST.get('loading_time')
                    products.update(loading_time=loading_time)
            
            # تغییر سایر اطلاعات
            if 'enable_other' in request.POST:
                if request.POST.get('weight'):
                    weight = int(request.POST.get('weight'))
                    products.update(weight=weight)
                
                if request.POST.get('description'):
                    description = request.POST.get('description')
                    products.update(description=description)
                    
            return redirect('cargo_product_list')
        
        # رندر صفحه ویرایش گروهی با محصولات انتخاب شده
        products_ids_str = ','.join([str(product.id) for product in products])
        vared_konandehs = VaredKonandeh.objects.all()
        barbaries = Barbary.objects.all()
        
        return render(request, 'bulk_edit_cargo_products.html', {
            'products': products,
            'ports': CargoProduct.PORTS,
            'countries': CargoProduct.COUNTRIES,
            'product_types': CargoProduct.PRODUCT_TYPES,
            'products_ids_str': products_ids_str,
            'vared_konandehs': vared_konandehs,
            'barbaries': barbaries
        })
    
    # اگر درخواست GET باشد، به صفحه لیست برگرد
    return redirect('cargo_product_list')

@role_required('admin', 'logistics_manager')
@login_required
def bulk_edit_purchase_cargo(request):
    """
    ویرایش گروهی کوتاژ برای خریدهای انتخاب شده
    """
    logger.warning(f"ویرایش گروهی کوتاژ برای خریدهای انتخاب شده: {get_client_ip(request)}, user: {request.user}")
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'روش درخواست نامعتبر است'}, status=405)
    
    try:
        # دریافت شناسه‌های خریدها
        purchase_ids_str = request.POST.get('purchase_ids', '')
        if not purchase_ids_str:
            return JsonResponse({'status': 'error', 'message': 'شناسه‌های خرید ارسال نشده است'}, status=400)
        
        purchase_ids = [pid for pid in purchase_ids_str.split(',') if pid]
        
        # شناسه کوتاژ
        cargo_id = request.POST.get('cargo_id')
        cargo = None
        
        # بررسی اگر کوتاژ با آی‌دی ارسال شده وجود دارد
        if cargo_id:
            try:
                cargo = CargoProduct.objects.get(id=cargo_id)
            except CargoProduct.DoesNotExist:
                # اگر cargo_id داده شده ولی وجود ندارد
                return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
        
        # اگر حالت ایجاد کوتاژ جدید است
        cottage = request.POST.get('cottage')
        if not cargo_id and cottage:
            # بررسی اینکه آیا کوتاژی با این شماره قبلاً وجود دارد
            existing_cargo = CargoProduct.objects.filter(cottage=cottage).first()
            if existing_cargo:
                return JsonResponse({'status': 'error', 'message': f'کوتاژی با شماره {cottage} قبلاً وجود دارد'}, status=400)
            
            # دریافت اطلاعات وارد کننده و باربری
            vared_konandeh_id = request.POST.get('vared_konandeh')
            barbary_id = request.POST.get('barbary')
            
            vared_konandeh = None
            if vared_konandeh_id:
                try:
                    vared_konandeh = VaredKonandeh.objects.get(id=vared_konandeh_id)
                except VaredKonandeh.DoesNotExist:
                    pass
            
            barbary = None
            if barbary_id:
                try:
                    barbary = Barbary.objects.get(id=barbary_id)
                except Barbary.DoesNotExist:
                    pass
                
            # ایجاد کوتاژ جدید
            cargo = CargoProduct(
                cottage=cottage,
                type=request.POST.get('type', 'bazaargah'),
                company_price=int(request.POST.get('company_price', 0)),
                customer_price=int(request.POST.get('customer_price', 0)),
                product_type=request.POST.get('product_type', 'corn'),
                country=request.POST.get('country', 'iran'),
                vared_konandeh=vared_konandeh,
                barbary=barbary,
                weight=int(request.POST.get('weight', 100000)),
                status=request.POST.get('status') == 'on'
            )
            cargo.save()
        elif not cargo:
            # اگر نه cargo_id وجود دارد و نه اطلاعات کافی برای ایجاد کوتاژ جدید
            return JsonResponse({'status': 'error', 'message': 'اطلاعات کافی برای ایجاد یا انتخاب کوتاژ ارسال نشده است'}, status=400)
            
        # به‌روزرسانی فیلدهای کوتاژ اگر مقادیر جدید در درخواست ارسال شده باشد
        if cargo_id:  # تنها اگر کوتاژ موجود را ویرایش می‌کنیم
            if cottage:
                cargo.cottage = cottage
            
            if 'type' in request.POST and request.POST.get('type'):
                cargo.type = request.POST.get('type')
            
            if 'company_price' in request.POST and request.POST.get('company_price'):
                cargo.company_price = int(request.POST.get('company_price'))
            
            if 'customer_price' in request.POST and request.POST.get('customer_price'):
                cargo.customer_price = int(request.POST.get('customer_price'))
            
            if 'product_type' in request.POST and request.POST.get('product_type'):
                cargo.product_type = request.POST.get('product_type')
            
            if 'country' in request.POST and request.POST.get('country'):
                cargo.country = request.POST.get('country')
            
            # به‌روزرسانی وارد کننده و باربری
            if 'vared_konandeh' in request.POST and request.POST.get('vared_konandeh'):
                try:
                    cargo.vared_konandeh = VaredKonandeh.objects.get(id=request.POST.get('vared_konandeh'))
                except VaredKonandeh.DoesNotExist:
                    cargo.vared_konandeh = None
            
            if 'barbary' in request.POST and request.POST.get('barbary'):
                try:
                    cargo.barbary = Barbary.objects.get(id=request.POST.get('barbary'))
                except Barbary.DoesNotExist:
                    cargo.barbary = None
            
            if 'weight' in request.POST and request.POST.get('weight'):
                cargo.weight = int(request.POST.get('weight'))
            
            if 'status' in request.POST:
                cargo.status = request.POST.get('status') == 'on'
            
            # ذخیره تغییرات کوتاژ
            cargo.save()
        
        # تعداد خریدهای به‌روزرسانی شده
        from core._models import Purchase
        updated_count = 0
        
        # به‌روزرسانی خریدهای انتخاب شده
        purchases = Purchase.objects.filter(id__in=purchase_ids)
        for purchase in purchases:
            purchase.cargo = cargo
            purchase.save()
            updated_count += 1
        
        return JsonResponse({
            'status': 'success',
            'message': f'کوتاژ {cargo.cottage} در {updated_count} خرید اعمال شد.',
            'updated_count': updated_count
        })
    
    except ValueError as e:
        logger.error(f"خطای مقدار: {str(e)}, ip: {get_client_ip(request)}, user: {request.user}")
        return JsonResponse({'status': 'error', 'message': f'خطای مقدار: {str(e)}'}, status=400)
    except Exception as e:
        logger.error(f"خطای عمومی: {str(e)}, ip: {get_client_ip(request)}, user: {request.user}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_cargo_product_details(request):
    """
    دریافت اطلاعات کوتاژ براساس شماره کوتاژ
    """
    logger.warning(f"دریافت اطلاعات کوتاژ: {get_client_ip(request)}, user: {request.user}")
    cottage = request.GET.get('cottage', '')
    
    if not cottage:
        return JsonResponse({'status': 'error', 'message': 'شماره کوتاژ ارسال نشده است'}, status=400)
    
    try:
        cargo = CargoProduct.objects.select_related('vared_konandeh', 'barbary').get(cottage=cottage)
        
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        hide_supplier_info = user_role in ['sales_agent', 'support_agent']
        
        # ساخت دیکشنری از داده‌های کوتاژ
        cargo_data = {
            'id': cargo.id,
            'cottage': cargo.cottage,
            'type': cargo.type,
            'customer_price': cargo.customer_price,
            'product_type': cargo.product_type,
            'country': cargo.country,
            'barbary_id': cargo.barbary_id if cargo.barbary else None,
            'barbary_name': cargo.barbary.name if cargo.barbary else None,
            'port': cargo.port,
            'loading_time': cargo.loading_time,
            'weight': cargo.weight,
            'status': cargo.status,
            'description': cargo.description
        }
        
        # اضافه کردن اطلاعات حساس فقط برای نقش‌های مجاز
        if not hide_supplier_info:
            cargo_data.update({
                'company_price': cargo.company_price,
                'vared_konandeh_id': cargo.vared_konandeh_id if cargo.vared_konandeh else None,
                'vared_konandeh_name': cargo.vared_konandeh.name if cargo.vared_konandeh else None,
            })
        
        return JsonResponse({'status': 'success', 'cargo': cargo_data})
    
    except CargoProduct.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def list_cargo_products(request):
    """
    دریافت لیست کوتاژهای فعال
    """
    try:
        # فیلتر جستجو
        search_term = request.GET.get('q', '')
        
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        hide_supplier_info = user_role in ['sales_agent', 'support_agent']
        
        # دریافت کوتاژهای فعال با یا بدون اطلاعات واردکننده
        if hide_supplier_info:
            query = CargoProduct.objects.filter(status=True).select_related('barbary')
        else:
            query = CargoProduct.objects.filter(status=True).select_related('vared_konandeh', 'barbary')
        
        # اعمال جستجو اگر عبارت جستجو ارسال شده باشد
        if search_term:
            search_filters = Q(cottage__icontains=search_term) | Q(product_type__icontains=search_term) | Q(country__icontains=search_term) | Q(barbary__name__icontains=search_term)
            
            # اضافه کردن جستجو در نام واردکننده فقط برای نقش‌های مجاز
            if not hide_supplier_info:
                search_filters |= Q(vared_konandeh__name__icontains=search_term)
                
            query = query.filter(search_filters)
        
        # محدود کردن تعداد نتایج برای بهبود کارایی
        cargos = query.order_by('-created_at')[:100]
        
        # ساخت لیست از داده‌های کوتاژها
        cargos_data = []
        for cargo in cargos:
            cargo_info = {
                'id': cargo.id,
                'cottage': cargo.cottage,
                'product_type': cargo.get_product_type_display(),
                'country': cargo.get_country_display(),
                'barbary': cargo.barbary.name if cargo.barbary else '',
                'weight': cargo.weight
            }
            
            # اضافه کردن اطلاعات واردکننده فقط برای نقش‌های مجاز
            if not hide_supplier_info:
                cargo_info['vared_konandeh'] = cargo.vared_konandeh.name if cargo.vared_konandeh else ''
            
            cargos_data.append(cargo_info)
        
        return JsonResponse({'status': 'success', 'cargos': cargos_data})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
