from django.urls import path
from . import views

app_name = 'whatsapp_api'

urlpatterns = [
    # Dashboard and main send page
    path('whatsapp-dashboard/', views.whatsapp_dashboard, name='whatsapp-dashboard'),
    path('send-whatsapp/', views.send_whatsapp, name='send-whatsapp'),
    path('history/', views.message_history, name='message-history'),
    
    # Queue management URLs
    path('queue/', views.whatsapp_queue, name='whatsapp-queue'),
    path('queue/<int:whatsapp_id>/', views.whatsapp_detail, name='whatsapp_detail'),
    path('queue/<int:whatsapp_id>/edit/', views.edit_whatsapp, name='edit_whatsapp'),
    path('queue/<int:whatsapp_id>/delete/', views.delete_whatsapp, name='delete_whatsapp'),
    path('queue/<int:whatsapp_id>/suspend/', views.suspend_whatsapp, name='suspend_whatsapp'),
    path('queue/<int:whatsapp_id>/resume/', views.resume_whatsapp, name='resume_whatsapp'),
    path('queue/<int:whatsapp_id>/send-now/', views.send_whatsapp_now, name='send_whatsapp_now'),
    path('queue/<int:whatsapp_id>/retry/', views.retry_whatsapp, name='retry_whatsapp'),
    path('queue/process-manually/', views.process_whatsapp_queue_manually, name='process_whatsapp_queue_manually'),
    
    # Template management URLs
    path('templates/', views.templates, name='templates'),
    path('templates/list/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/edit/<int:template_id>/', views.template_edit, name='template_edit'),
    path('templates/detail/<int:template_id>/', views.template_detail, name='template_detail'),
    path('templates/delete/<int:template_id>/', views.template_delete, name='template_delete'),
    path('templates/set-default/<int:template_id>/', views.set_template_default, name='set_template_default'),
    path('templates/preview/<int:template_id>/', views.template_preview, name='template_preview'),
    path('templates/test/<int:template_id>/', views.template_test, name='template_test'),
    path('templates/check/', views.template_check, name='template_check'),
    
    # API endpoints
    path('api/templates/get-for-status/', views.get_templates_for_status, name='get_templates_for_status'),
    path('api/templates/get-by-type/', views.get_templates_by_type, name='get_templates_by_type'),
    path('api/customer-purchases/', views.get_customer_purchases, name='get_customer_purchases'),
]
