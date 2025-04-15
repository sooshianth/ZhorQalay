from django.urls import path
from . import views

app_name = 'excel_manager'

urlpatterns = [
    
    # URL‌های مدیریت فایل‌های اکسل بازارگاه
    path('bge/', views.bge_files_list, name='bge_files_list'),
    path('bge/upload/', views.upload_bge_file, name='upload_bge_file'),
    path('bge/process/<int:file_id>/', views.process_bge_file, name='process_bge_file'),
    
    # API‌های مدیریت فایل‌های اکسل
    path('api/search-cargo-products/', views.search_cargo_products, name='search_cargo_products'),
] 