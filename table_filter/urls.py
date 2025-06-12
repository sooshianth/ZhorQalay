from django.urls import path
from . import views

app_name = 'table_filter'

urlpatterns = [
    path('demo/', views.table_filter_demo, name='demo'),
    path('bulk-edit/', views.bulk_edit_view, name='bulk_edit'),
    path('bulk-edit-excel/', views.bulk_edit_excel_view, name='bulk_edit_excel'),
    path('bulk-edit-template/', views.download_excel_template_view, name='bulk_edit_template'),
    path('bulk-edit-page/', views.bulk_edit_page, name='bulk_edit_page'),
    path('bulk-edit-excel-page/', views.bulk_edit_excel_page, name='bulk_edit_excel_page'),
    path('edit-history/', views.edit_history_view, name='edit_history'),
    path('edit-history/<str:app_name>/<str:model_name>/<str:object_id>/', views.object_edit_history_view, name='object_edit_history'),
    path('restore-field/<int:log_id>/', views.restore_field_view, name='restore_field'),
    
    # API endpoints
    path('api/edit-history/', views.edit_history_api, name='edit_history_api'),
    path('api/restore-value/', views.restore_value_api, name='restore_value_api'),
    path('debug-excel/', views.debug_excel_processing, name='debug_excel'),
] 