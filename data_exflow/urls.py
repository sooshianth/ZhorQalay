from django.urls import path
from . import views

app_name = 'data_exflow'

urlpatterns = [
    # Import URLs
    path('import/', views.import_view, name='import'),
    path('import/upload/', views.import_upload, name='import_upload'),
    path('import/preview/<uuid:session_id>/', views.import_preview, name='import_preview'),
    path('import/map-fields/<uuid:session_id>/', views.import_map_fields, name='import_map_fields'),
    path('import/validate/<uuid:session_id>/', views.import_validate, name='import_validate'),
    path('import/process/<uuid:session_id>/', views.import_process, name='import_process'),
    path('import/results/<uuid:session_id>/', views.import_results, name='import_results'),
    path('import/revert/<uuid:session_id>/', views.import_revert, name='import_revert'),
    
    # Export URLs
    path('export/', views.export_view, name='export'),
    path('export/select-fields/', views.export_select_fields, name='export_select_fields'),
    path('export/process/', views.export_process, name='export_process'),
    
    # API endpoints for AJAX requests
    path('api/models/', views.api_get_models, name='api_get_models'),
    path('api/model-fields/<str:app_label>/<str:model_name>/', views.api_get_model_fields, name='api_get_model_fields'),
    path('api/edit-cell/<uuid:session_id>/', views.api_edit_cell, name='api_edit_cell'),
]
