from django.shortcuts import render, redirect
from core._models import CargoProduct
from django.contrib.auth.decorators import login_required

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

@login_required
def bulk_edit_cargo_products(request):
    if request.method == 'POST':
        product_ids = request.POST.getlist('product_ids')
        products = CargoProduct.objects.filter(id__in=product_ids)
        if 'status' in request.POST:
            status = request.POST.get('status') == 'on'
            products.update(status=status)
        return redirect('cargo_product_list')
    return render(request, 'bulk_edit_cargo_products.html', {'products': products})
