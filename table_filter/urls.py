from django.urls import path
from . import views, filter_views

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
    
    # =================== NEW FILTER API URLs ===================
    
    # پیکربندی جدول
    path('api/config/<str:table_name>/', filter_views.get_table_configuration, name='get_table_config'),
    path('api/setup-config/', filter_views.setup_table_configuration, name='setup_table_config'),
    path('api/update-column-config/', filter_views.update_column_configuration, name='update_column_config'),
    path('api/bulk-column-visibility/', filter_views.bulk_update_column_visibility, name='bulk_column_visibility'),
    path('api/column-order/', filter_views.update_column_order, name='update_column_order'),
    path('api/reset-column-order/', filter_views.reset_column_order, name='reset_column_order'),
    
    # اعمال فیلتر و مرتب‌سازی
    path('api/apply-filter/', filter_views.apply_table_filter, name='apply_filter'),
    path('api/column-values/<str:table_name>/<str:column_id>/', 
         filter_views.get_column_values, name='get_column_values'),
    
    # مدیریت وضعیت کاربر
    path('api/save-state/', filter_views.save_user_filter_state, name='save_filter_state'),
    path('api/get-state/<str:table_name>/', filter_views.get_user_filter_state, name='get_filter_state'),
    path('api/clear-state/<str:table_name>/', filter_views.clear_user_filter_state, name='clear_filter_state'),
    
    # آمار و تحلیل
    path('api/table-stats/<str:table_name>/', filter_views.get_table_stats, name='get_table_stats'),
    path('api/filter-stats/<str:table_name>/', filter_views.get_filter_stats, name='get_filter_stats'),
    path('api/detect-type/<str:table_name>/<str:column_id>/', 
         filter_views.detect_column_type, name='detect_column_type'),
    
    # پیش‌تنظیمات فیلتر
    path('api/presets/<str:table_name>/', filter_views.get_filter_presets, name='get_filter_presets'),
    path('api/save-preset/', filter_views.save_filter_preset, name='save_filter_preset'),
    path('api/delete-preset/<int:preset_id>/', filter_views.delete_filter_preset, name='delete_filter_preset'),
    path('api/apply-preset/<int:preset_id>/', filter_views.apply_filter_preset, name='apply_filter_preset'),
    
    # صفحات کمکی
    path('filter-demo/', filter_views.table_filter_demo, name='filter_demo'),
    path('excel-demo/', views.excel_filter_demo, name='excel_filter_demo'),
] 