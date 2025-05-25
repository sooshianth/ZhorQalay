from django.urls import path
from . import views

urlpatterns = [
    path('send-whatsapp/', views.send_whatsapp, name='send-whatsapp'),
    path('whatsapp-dashboard/', views.whatsapp_dashboard, name='whatsapp-dashboard'),
    path('history/', views.message_history, name='message-history'),
    path('templates/', views.templates, name='templates'),
    path('queue/', views.whatsapp_queue, name='whatsapp-queue'),
    
    # Template management URLs
    path('templates/list/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/edit/<int:template_id>/', views.template_edit, name='template_edit'),
    path('templates/detail/<int:template_id>/', views.template_detail, name='template_detail'),
    path('templates/delete/<int:template_id>/', views.template_delete, name='template_delete'),
    path('templates/set-default/<int:template_id>/', views.set_template_default, name='set_template_default'),
    path('templates/preview/<int:template_id>/', views.template_preview, name='template_preview'),
    path('templates/test/<int:template_id>/', views.template_test, name='template_test'),
    path('templates/get-for-status/', views.get_templates_for_status, name='get_templates_for_status'),
]
