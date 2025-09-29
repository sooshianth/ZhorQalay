from django.shortcuts import render
from core._models import CargoProduct
from major.models import NonBazargahProduct
from django.contrib.auth.decorators import login_required
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from .cargo_product_CRUD_panel import get_client_ip
import logging

logger = logging.getLogger("bki_cargos_cargo_product_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def cargo_product_list(request):
    logger.warning(f"لیست محصولات: {get_client_ip(request)}, user: {request.user}")
    user_role = determine_user_role(request.user)
    
    # تشخیص محدودیت‌های نمایش بر اساس نقش کاربر
    hide_supplier_info = user_role in ['sales_agent']
    
    # برای کارشناسان فروش و پیگیری، اطلاعات واردکننده را مخفی می‌کنیم
    if hide_supplier_info:
        # برای کارشناس فروش و پیگیری، صرفا محصولات را بدون اطلاعات واردکننده ارسال می‌کنیم
        cargo_products = CargoProduct.objects.filter(status=True)
        deactive_cargo_products = CargoProduct.objects.filter(status=False)
        non_bazargah_products = NonBazargahProduct.objects.filter(status=True)
        deactive_non_bazargah_products = NonBazargahProduct.objects.filter(status=False)
    else:
        # برای سایر نقش‌ها، اطلاعات کامل شامل واردکننده ارسال می‌شود
        cargo_products = CargoProduct.objects.filter(status=True).select_related('vared_konandeh', 'barbary')
        deactive_cargo_products = CargoProduct.objects.filter(status=False).select_related('vared_konandeh', 'barbary')
        non_bazargah_products = NonBazargahProduct.objects.filter(status=True).select_related('vared_konandeh')
        deactive_non_bazargah_products = NonBazargahProduct.objects.filter(status=False).select_related('vared_konandeh')
    
    logger.warning(cargo_products)
    return render(request, 'cargo_product_view.html', {
        'cargo_products': cargo_products, 
        'deactive_cargo_products': deactive_cargo_products, 
        'non_bazargah_products': non_bazargah_products,
        'deactive_non_bazargah_products': deactive_non_bazargah_products,
        'user_role': user_role,
        'hide_supplier_info': hide_supplier_info  # متغیر برای مخفی کردن اطلاعات واردکننده
    })



