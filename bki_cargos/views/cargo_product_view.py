from django.shortcuts import render
from core._models import CargoProduct
from django.contrib.auth.decorators import login_required

@login_required
def cargo_product_list(request):
    cargo_products = CargoProduct.objects.filter(status=True)
    deactive_cargo_products = CargoProduct.objects.filter(status=False)
    return render(request, 'cargo_product_view.html', {'cargo_products': cargo_products, 'deactive_cargo_products': deactive_cargo_products})



