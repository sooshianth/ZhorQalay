from django.urls import path
from . import views

app_name = 'excel_manager'

urlpatterns = [
    
    # URL‌های مدیریت فایل‌های اکسل بازارگاه
    path('bge/', views.bge_files_list, name='bge_files_list'),
    path('bge/upload/', views.upload_bge_file, name='upload_bge_file'),
    path('bge/process/<int:file_id>/', views.process_bge_file, name='process_bge_file'),
    path('bge/approve/<int:file_id>/', views.approve_bge_file, name='approve_bge_file'),
    path('excel/view/<int:file_id>/', views.view_excel_file, name='view_excel_file'),
    path('excel/delete/<int:file_id>/', views.delete_excel_file, name='delete_excel_file'),
    # API‌های مدیریت فایل‌های اکسل
    path('api/search-cargo-products/', views.search_cargo_products, name='search_cargo_products'),
    
    # ذخیره تغییرات اکسل
    path('excel/save-changes/<int:file_id>/', views.save_excel_changes, name='save_excel_changes'),
] 