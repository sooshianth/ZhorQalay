from django.urls import path
from django.views.generic.base import RedirectView


from .views import (
    cargo_product_view,
    managers_login,
    managers_logout, 
    purchase_CRUD_view, 
    managers_profile_view, 
    purchase_list_view,
    notification_view,
    bulk_purchase_edit,
    cargo_product_CRUD_panel,
)

urlpatterns = [
    path('cargo-products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('cargo-product/add/', cargo_product_CRUD_panel.cargo_product_crud_panel, name='cargo_product_crud_panel'),
    path('cargo-product/edit/<int:product_id>/', cargo_product_CRUD_panel.cargo_product_crud_panel, name='cargo_product_crud_panel'),
    path('cargo-product/bulk-edit/', cargo_product_CRUD_panel.bulk_edit_cargo_products, name='bulk_edit_cargo_products'),
    path('cargo-product/details/', cargo_product_CRUD_panel.get_cargo_product_details, name='cargo_product_details'),
    path('cargo-products/list/', cargo_product_CRUD_panel.list_cargo_products, name='list_cargo_products'),
    path('financial_manager_login/', managers_login.financial_manager_login_view, name='financial_manager_login'),
    path('logistics_manager_login/', managers_login.logistics_manager_login_view, name='logistics_manager_login'),
    path('support_agent_login/', managers_login.support_agent_login_view, name='support_agent_login'),
    path('logout/', managers_logout.logout_view, name='logout'),

    path('logistics_manager_profile/', managers_profile_view.logistics_manager_profile_view, name='logistics_manager_profile'),
    path('financial_manager_profile/', managers_profile_view.financial_manager_profile_view, name='financial_manager_profile'),
    path('support_agent_profile/', managers_profile_view.support_agent_profile_view, name='support_agent_profile'),

    path('purchase_list/', purchase_list_view.purchase_list, name='purchase_list' ),
    path('purchases/update-columns/', purchase_list_view.update_columns, name='update_columns'),
    path('purchases/export/', purchase_list_view.export_to_excel, name='export_purchases'),
    path('purchases/update-field/', purchase_list_view.update_purchase_field, name='update_purchase_field'),
    path('purchases/revert-edit/', purchase_list_view.revert_purchase_edit, name='revert_purchase_edit'),
    path('purchases/<int:purchase_id>/edit-logs/', purchase_list_view.get_purchase_edit_logs, name='purchase_edit_logs'),

    path('purchase_CRUD/<int:purchase_id>/', purchase_CRUD_view.purchase_CRUD_view, name='purchase_CRUD'),
    path('purchase_delete/<int:purchase_id>/', purchase_CRUD_view.delete_purchase_view, name='purchase_delete' ),
    path('purchase_pdf/<int:purchase_id>/', purchase_CRUD_view.generate_purchase_pdf, name='purchase_pdf'),
    path('upload_purchase_document/<int:purchase_id>/', purchase_CRUD_view.upload_purchase_document, name='upload_purchase_document'),

    path('purchase_CRUD/notifications/', notification_view.get_notifications, name='get_notifications'),
    path('purchase_CRUD/notifications/<int:notification_id>/read/', notification_view.mark_notification_read, name='mark_notification_read'),

    path('bulk-purchase-edit/', bulk_purchase_edit.bulk_purchase_edit, name='bulk_purchase_edit'),
    path('bulk-purchase-edit/upload-excel/', bulk_purchase_edit.upload_excel, name='bulk_purchase_upload_excel'),
    path('bulk-purchase-edit/apply/', bulk_purchase_edit.apply_bulk_edit, name='bulk_purchase_apply_edit'),
    path('bulk-purchase-edit/details/<int:purchase_id>/', bulk_purchase_edit.get_purchase_details, name='bulk_purchase_details'),
    path('bulk-purchase-edit/export/', bulk_purchase_edit.export_purchase_list, name='bulk_purchase_export'),
    path('bulk-edit-cargo/', cargo_product_CRUD_panel.bulk_edit_purchase_cargo, name='bulk_edit_purchase_cargo'),
]