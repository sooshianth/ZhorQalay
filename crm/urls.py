from django.urls import path
from django.views.generic.base import RedirectView

from .views import managers_login, managers_logout, purchase_CRUD_view, managers_profile_view, purchase_list_view, bgef_view

urlpatterns = [
    path('financial_manager_login/', managers_login.financial_manager_login_view, name='financial_manager_login'),
    path('logistics_manager_login/', managers_login.logistics_manager_login_view, name='logistics_manager_login'),
    path('logout/', managers_logout.logout_view, name='logout'),
    path('logistics_manager_profile/', managers_profile_view.logistics_manager_profile_view, name='logistics_manager_profile'),
    path('financial_manager_profile/', managers_profile_view.financial_manager_profile_view, name='financial_manager_profile'),
    path('purchase_CRUD/<int:purchase_id>/', purchase_CRUD_view.purchase_CRUD_view, name='purchase_CRUD'),
    path('purchase_list/', purchase_list_view.purchase_list, name='purchase_list' ),
    path('bgef/', bgef_view.upload_bge_file_view, name='BGEF' ),
    path('api/search-cargo-products/', bgef_view.search_cargo_products, name='search_cargo_products'),
    path('bge-files/', bgef_view.logistics_bge_files_view, name='logistics_bge_files'),
    path('logistics/preview-bge-file/<int:file_id>/', bgef_view.preview_bge_file, name='preview_bge_file'),
    path('logistics/approve-bge-file/<int:file_id>/', bgef_view.approve_bge_file, name='approve_bge_file'),
    path('logistics/download-bge-file/<int:file_id>/', bgef_view.download_bge_file, name='download_bge_file'),
    path('preview_bge_file/<int:file_id>/', bgef_view.preview_bge_file, name='preview_bge_file'),
]