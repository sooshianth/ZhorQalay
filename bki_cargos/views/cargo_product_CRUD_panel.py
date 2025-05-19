from django.shortcuts import render, redirect
from core._models import CargoProduct
from django.contrib.auth.decorators import login_required
from core.decorators.decorators import role_required
from django.http import JsonResponse
from django.db.models import Q

@role_required('admin', 'logistics_manager')
@login_required
def cargo_product_crud_panel(request, product_id=None):
    product = None
    if product_id:
        product = CargoProduct.objects.get(id=product_id)
    if request.method == 'POST':
        data = request.POST
        if product:
            # Update existing product
            product.type = data.get('type')
            product.cottage = data.get('cottage')
            product.company_price = data.get('company_price')
            product.customer_price = data.get('customer_price')
            product.product_type = data.get('product_type')
            product.country = data.get('country')
            product.importer_name = data.get('importer_name')
            product.port = data.get('port')
            product.loading_time = data.get('loading_time')
            product.description = data.get('description')
            product.weight = data.get('weight')
            product.status = data.get('status') == 'on'
            product.save()
        else:
            # Create new product
            CargoProduct.objects.create(
                type=data.get('type'),
                cottage=data.get('cottage'),
                company_price=data.get('company_price'),
                customer_price=data.get('customer_price'),
                product_type=data.get('product_type'),
                country=data.get('country'),
                importer_name=data.get('importer_name'),
                port=data.get('port'),
                loading_time=data.get('loading_time'),
                description=data.get('description'),
                weight=data.get('weight'),
                status=data.get('status') == 'on'
            )
        return redirect('cargo_product_list')
    return render(request, 'cargo_product_crud_panel.html', {'product': product, 'purchase_types': CargoProduct.PURCHASE_TYPES, 'product_types': CargoProduct.PRODUCT_TYPES, 'countries': CargoProduct.COUNTRIES, 'ports': CargoProduct.PORTS})

@role_required('admin', 'logistics_manager')
@login_required
def bulk_edit_cargo_products(request):
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
                    company_price = int(request.POST.get('company_price'))
                    products.update(company_price=company_price)
                    
                if request.POST.get('customer_price'):
                    customer_price = int(request.POST.get('customer_price'))
                    products.update(customer_price=customer_price)
            
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
        return render(request, 'bulk_edit_cargo_products.html', {
            'products': products,
            'ports': CargoProduct.PORTS,
            'products_ids_str': products_ids_str
        })
    
    # اگر درخواست GET باشد، به صفحه لیست برگرد
    return redirect('cargo_product_list')

@role_required('admin', 'logistics_manager')
@login_required
def bulk_edit_purchase_cargo(request):
    """
    ویرایش گروهی کوتاژ برای خریدهای انتخاب شده
    """
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
                
            # ایجاد کوتاژ جدید
            cargo = CargoProduct(
                cottage=cottage,
                type=request.POST.get('type', 'bazaargah'),
                company_price=int(request.POST.get('company_price', 0)),
                customer_price=int(request.POST.get('customer_price', 0)),
                product_type=request.POST.get('product_type', 'corn'),
                country=request.POST.get('country', 'iran'),
                importer_name=request.POST.get('importer_name', ''),
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
            
            if 'importer_name' in request.POST and request.POST.get('importer_name'):
                cargo.importer_name = request.POST.get('importer_name')
            
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
        return JsonResponse({'status': 'error', 'message': f'خطای مقدار: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_cargo_product_details(request):
    """
    دریافت اطلاعات کوتاژ براساس شماره کوتاژ
    """
    cottage = request.GET.get('cottage', '')
    
    if not cottage:
        return JsonResponse({'status': 'error', 'message': 'شماره کوتاژ ارسال نشده است'}, status=400)
    
    try:
        cargo = CargoProduct.objects.get(cottage=cottage)
        
        # ساخت دیکشنری از داده‌های کوتاژ
        cargo_data = {
            'id': cargo.id,
            'cottage': cargo.cottage,
            'type': cargo.type,
            'company_price': cargo.company_price,
            'customer_price': cargo.customer_price,
            'product_type': cargo.product_type,
            'country': cargo.country,
            'importer_name': cargo.importer_name,
            'port': cargo.port,
            'loading_time': cargo.loading_time,
            'weight': cargo.weight,
            'status': cargo.status,
            'description': cargo.description
        }
        
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
        
        # دریافت کوتاژهای فعال
        query = CargoProduct.objects.filter(status=True)
        
        # اعمال جستجو اگر عبارت جستجو ارسال شده باشد
        if search_term:
            query = query.filter(
                Q(cottage__icontains=search_term) |
                Q(product_type__icontains=search_term) |
                Q(country__icontains=search_term) |
                Q(importer_name__icontains=search_term)
            )
        
        # محدود کردن تعداد نتایج برای بهبود کارایی
        cargos = query.order_by('-created_at')[:100]
        
        # ساخت لیست از داده‌های کوتاژها
        cargos_data = []
        for cargo in cargos:
            cargos_data.append({
                'id': cargo.id,
                'cottage': cargo.cottage,
                'product_type': cargo.get_product_type_display(),
                'country': cargo.get_country_display(),
                'importer_name': cargo.importer_name or '',
                'weight': cargo.weight
            })
        
        return JsonResponse({'status': 'success', 'cargos': cargos_data})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
