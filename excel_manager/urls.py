from django.urls import path
from . import views

app_name = 'excel_manager'

urlpatterns = [
    # URL‌های مدیریت فایل‌های اکسل
    path('', views.excel_files_list, name='excel_files_list'),
    path('upload/', views.upload_excel_file, name='upload_excel_file'),
    path('detail/<int:file_id>/', views.excel_file_detail, name='excel_file_detail'),
    path('preview/<int:file_id>/', views.preview_excel_file, name='preview_excel_file'),
    path('process/<int:file_id>/', views.process_excel_file, name='process_excel_file'),
    path('approve/<int:file_id>/', views.approve_excel_file, name='approve_excel_file'),
    path('download/<int:file_id>/', views.download_excel_file, name='download_excel_file'),
    path('delete/<int:file_id>/', views.delete_excel_file, name='delete_excel_file'),
    
    # URL‌های مدیریت فایل‌های اکسل بازارگاه
    path('bge/', views.bge_files_list, name='bge_files_list'),
    path('bge/upload/', views.upload_bge_file, name='upload_bge_file'),
    path('bge/process/<int:file_id>/', views.process_bge_file, name='process_bge_file'),
    
    # API‌های مدیریت فایل‌های اکسل
    path('api/search-cargo-products/', views.search_cargo_products, name='search_cargo_products'),
] 