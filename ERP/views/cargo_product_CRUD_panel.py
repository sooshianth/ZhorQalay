from django.shortcuts import render, redirect
from core._models import CargoProduct
from django.contrib.auth.decorators import login_required
from core.decorators.decorators import role_required

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
