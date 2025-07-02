from django.urls import path
from django.views.generic.base import RedirectView


from .views import (
    purchase_CRUD_view, 
    managers_profile_view, 
    purchase_list_view,
    notification_view,
    bulk_purchase_edit,
    purchase_filter_api,
)

urlpatterns = [

    path('logistics_manager_profile/', managers_profile_view.logistics_manager_profile_view, name='logistics_manager_profile'),
    path('financial_manager_profile/', managers_profile_view.financial_manager_profile_view, name='financial_manager_profile'),
    path('support_agent_profile/', managers_profile_view.support_agent_profile_view, name='support_agent_profile'),

    path('purchase_list/', purchase_list_view.purchase_list, name='purchase_list' ),
    path('purchases/archived/', purchase_list_view.load_archived_purchases, name='load_archived_purchases'),
    path('purchases/update-columns/', purchase_list_view.update_columns, name='update_columns'),
    path('update_column_order/', purchase_list_view.update_column_order, name='update_column_order'),
    path('purchase/reset_column_order/', purchase_list_view.reset_column_order, name='reset_column_order'),
    path('purchases/clear-cache/', purchase_list_view.clear_column_cache, name='clear_column_cache'),
    path('purchases/export/', purchase_list_view.export_to_excel, name='export_purchases'),

    path('purchases/aggregated-stats/', purchase_list_view.get_purchase_aggregated_stats, name='purchase_aggregated_stats'),
    path('purchases/section-ids/', purchase_list_view.get_section_purchase_ids, name='get_section_purchase_ids'),
    path('cargo-products/list/', purchase_list_view.cargo_products_list, name='cargo_products_list'),
    path('cargo-product/details/', purchase_list_view.cargo_product_details, name='cargo_product_details'),
    path('bulk-edit-cargo/', purchase_list_view.bulk_edit_cargo, name='bulk_edit_cargo'),

    # APIهای فیلتر سمت سرور
    path('purchases/filter/config/', purchase_filter_api.get_purchase_table_configuration, name='purchase_filter_config'),
    path('purchases/filter/apply/', purchase_filter_api.apply_purchase_filter, name='apply_purchase_filter'),
    path('purchases/filter/column-values/', purchase_filter_api.get_purchase_column_values, name='purchase_column_values'),

    path('purchase_CRUD/<int:purchase_id>/', purchase_CRUD_view.purchase_CRUD_view, name='purchase_CRUD'),
    path('purchase_delete/<int:purchase_id>/', purchase_CRUD_view.delete_purchase_view, name='purchase_delete' ),
    path('purchase_pdf/<int:purchase_id>/', purchase_CRUD_view.generate_purchase_pdf, name='purchase_pdf'),
    path('upload_purchase_document/<int:purchase_id>/', purchase_CRUD_view.upload_purchase_document, name='upload_purchase_document'),
    path('link_bazaargah_purchase/<int:purchase_id>/', purchase_CRUD_view.link_bazaargah_purchase, name='link_bazaargah_purchase'),
    path('link_manual_purchase/<int:purchase_id>/', purchase_CRUD_view.link_manual_purchase, name='link_manual_purchase'),

    path('purchase_CRUD/notifications/', notification_view.get_notifications, name='get_notifications'),
    path('purchase_CRUD/notifications/<int:notification_id>/read/', notification_view.mark_notification_read, name='mark_notification_read'),

    path('bulk-purchase-edit/', bulk_purchase_edit.bulk_purchase_edit, name='bulk_purchase_edit'),
    path('bulk-purchase-edit/upload-excel/', bulk_purchase_edit.upload_excel, name='bulk_purchase_upload_excel'),
    path('bulk-purchase-edit/apply/', bulk_purchase_edit.apply_bulk_edit, name='bulk_purchase_apply_edit'),
    path('bulk-purchase-edit/details/<int:purchase_id>/', bulk_purchase_edit.get_purchase_details, name='bulk_purchase_details'),
    path('bulk-purchase-edit/export/', bulk_purchase_edit.export_purchase_list, name='bulk_purchase_export'),
]