from django.urls import path
from . import views

urlpatterns = [
    # صفحه اصلی لیست بارنامه‌ها
    path('', views.barnameh_list, name='barnameh_list'),
    
    # API های فیلتر و ستون‌ها
    path('api/filter/', views.apply_barnameh_filter, name='apply_barnameh_filter'),
    path('api/columns/<str:column_id>/', views.barnameh_column_values, name='barnameh_column_values'),
    
    # API های جدید برای مدیریت ستون‌ها
    path('api/columns/update/', views.update_barnameh_columns, name='update_barnameh_columns'),
    path('api/columns/reset/', views.reset_barnameh_columns, name='reset_barnameh_columns'),
    path('api/columns/config/', views.get_barnameh_columns_config, name='get_barnameh_columns_config'),
    
    # صفحات جزئیات و عملیات
    path('detail/<int:barnameh_id>/', views.barnameh_detail, name='barnameh_detail'),
    path('create/', views.barnameh_create, name='barnameh_create'),
    path('edit/<int:barnameh_id>/', views.barnameh_edit, name='barnameh_edit'),
    path('delete/<int:barnameh_id>/', views.barnameh_delete, name='barnameh_delete'),
    
    # عملیات اکسل
    path('upload-excel/', views.upload_excel, name='upload_excel'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('export-barnameh-excel/', views.export_barnameh_excel, name='export_barnameh_excel'),
    path('download-excel-template/', views.download_excel_template, name='download_excel_template'),
    
    # عملیات با بازارگاه
    path('send-to-bki/<int:barnameh_id>/', views.send_to_bki, name='send_to_bki'),
    path('bulk-send-to-bki/', views.bulk_send_to_bki, name='bulk_send_to_bki'),
    path('edit-barnameh-in-bki/<int:barnameh_id>/', views.edit_barnameh_in_bki, name='edit_barnameh_in_bki'),
    path('estelame-barnameh/<int:barnameh_id>/', views.estelame_barnameh_view, name='estelame_barnameh'),
    
    # عملیات گروهی
    path('bulk-edit/', views.bulk_edit, name='bulk_edit'),
    path('bulk-delete/', views.bulk_delete, name='bulk_delete'),
    
    # API
    path('api/', views.barnameh_api, name='barnameh_api'),
]

