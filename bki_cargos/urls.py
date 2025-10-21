from django.urls import path
from .views import cargo_product_view, cargo_product_CRUD_panel
from .views import barbary_view, vared_konandeh_view
from django.views.generic.base import RedirectView

urlpatterns = [
    path('cargo-products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('cargo-product/add/', cargo_product_CRUD_panel.cargo_product_crud_panel, name='cargo_product_crud_panel'),
    path('cargo-product/bulk-edit/', cargo_product_CRUD_panel.bulk_edit_cargo_products, name='bulk_edit_cargo_products'),
    path('cargo-product/details/', cargo_product_CRUD_panel.get_cargo_product_details, name='cargo_product_details'),
    path('cargo-products/list/', cargo_product_CRUD_panel.list_cargo_products, name='list_cargo_products'),
    path('bulk-edit-cargo/', cargo_product_CRUD_panel.bulk_edit_purchase_cargo, name='bulk_edit_purchase_cargo'),
    
    
    # باربری‌ها
    path('barbaries/', barbary_view.barbary_list, name='barbary_list'),
    path('barbary/add/', barbary_view.barbary_add, name='barbary_add'),
    path('barbary/bulk-edit/', barbary_view.bulk_edit_barbaries, name='bulk_edit_barbaries'),
    
    # واردکنندگان
    path('vared-konandehs/', vared_konandeh_view.vared_konandeh_list, name='vared_konandeh_list'),
    path('vared-konandeh/add/', vared_konandeh_view.vared_konandeh_add, name='vared_konandeh_add'),
    path('vared-konandeh/bulk-edit/', vared_konandeh_view.bulk_edit_vared_konandehs, name='bulk_edit_vared_konandehs'),
    
    # URL‌های مرتبط با ویرایش گروهی
    path('cargo-products/bulk-edit/', lambda request: RedirectView.as_view(url='/table_filter/bulk-edit-page/')(request), name='cargo_product_bulk_edit'),
    path('cargo-products/bulk-edit-excel/', lambda request: RedirectView.as_view(url='/table_filter/bulk-edit-excel-page/')(request), name='cargo_product_bulk_edit_excel'),
    path('cargo-products/bulk-edit-template/', lambda request: RedirectView.as_view(url='/table_filter/bulk-edit-template/')(request), name='cargo_product_bulk_edit_template'),
]

