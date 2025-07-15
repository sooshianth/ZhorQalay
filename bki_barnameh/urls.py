from django.urls import path, include, re_path
from . import views
from .excel_management.views import upload_excel_view, download_excel_template, export_excel_view

urlpatterns = [
    path('', views.barnameh_list, name='barnameh_list'),
    path('detail/<int:barnameh_id>/', views.barnameh_detail, name='barnameh_detail'),
    path('create/', views.barnameh_create, name='barnameh_create'),
    path('edit/<int:barnameh_id>/', views.barnameh_edit, name='barnameh_edit'),
    path('delete/<int:barnameh_id>/', views.barnameh_delete, name='barnameh_delete'),
    path('upload-excel/', views.upload_excel, name='upload_excel'),
    path('send-to-bki/<int:barnameh_id>/', views.send_to_bki, name='send_to_bki'),
    path('bulk-send-to-bki/', views.bulk_send_to_bki, name='bulk_send_to_bki'),
    path('bulk-edit/', views.bulk_edit, name='bulk_edit'),
    path('bulk-delete/', views.bulk_delete, name='bulk_delete'),
    path('api/', views.barnameh_api, name='barnameh_api'),
    path('download-excel-template/', views.download_excel_template, name='download_excel_template'),
    
    # مسیرهای جدید
    path('export-barnameh-excel/', views.export_barnameh_excel, name='export_barnameh_excel'),
    path('edit-in-bki/<int:barnameh_id>/', views.edit_barnameh_in_bki, name='edit_barnameh_in_bki'),
    path('estelam/<int:barnameh_id>/', views.estelame_barnameh_view, name='estelame_barnameh'),
    
    # API URLs for barnameh list filtering
    path('api/apply_barnameh_filter/', views.apply_barnameh_filter, name='apply_barnameh_filter'),
    path('api/barnameh_column_values/<str:column_id>/', views.barnameh_column_values, name='barnameh_column_values'),
    path('api/get_barnameh_column_values/', views.get_barnameh_column_values, name='get_barnameh_column_values'),
    
    # API endpoints for column management
    path('api/update-columns/', views.update_barnameh_columns, name='update_barnameh_columns'),
    path('api/reset-columns/', views.reset_barnameh_columns, name='reset_barnameh_columns'),
    path('api/columns-config/', views.get_barnameh_columns_config, name='get_barnameh_columns_config'),
]

