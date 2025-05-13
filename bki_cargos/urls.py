from django.urls import path
from .views import cargo_product_view, cargo_product_CRUD_panel

urlpatterns = [
    path('cargo-products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('cargo-product/add/', cargo_product_CRUD_panel.cargo_product_crud_panel, name='cargo_product_crud_panel'),
    path('cargo-product/edit/<int:product_id>/', cargo_product_CRUD_panel.cargo_product_crud_panel, name='cargo_product_crud_panel'),
    path('cargo-product/bulk-edit/', cargo_product_CRUD_panel.bulk_edit_cargo_products, name='bulk_edit_cargo_products'),
    path('cargo-product/details/', cargo_product_CRUD_panel.get_cargo_product_details, name='cargo_product_details'),
    path('cargo-products/list/', cargo_product_CRUD_panel.list_cargo_products, name='list_cargo_products'),
    path('bulk-edit-cargo/', cargo_product_CRUD_panel.bulk_edit_purchase_cargo, name='bulk_edit_purchase_cargo'),
    
]

