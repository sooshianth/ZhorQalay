from django.urls import path
from . import views

app_name = 'sms_api'

urlpatterns = [
    # صفحات اصلی مدیریت پیامک
    path('dashboard/', views.sms_dashboard, name='sms_dashboard'),
    path('support-dashboard/', views.support_dashboard, name='support_dashboard'),
    path('queue/', views.sms_queue, name='sms_queue'),
    path('logs/', views.sms_log, name='sms_log'),
    
    # افزودن و مدیریت پیامک
    path('create/', views.create_sms, name='create_sms'),
    path('detail/<int:sms_id>/', views.sms_detail, name='sms_detail'),
    path('edit/<int:sms_id>/', views.edit_sms, name='edit_sms'),
    
    # عملیات روی پیامک‌ها
    path('delete/<int:sms_id>/', views.delete_sms, name='delete_sms'),
    path('suspend/<int:sms_id>/', views.suspend_sms, name='suspend_sms'),
    path('resume/<int:sms_id>/', views.resume_sms, name='resume_sms'),
    path('send-now/<int:sms_id>/', views.send_sms_now, name='send_now'),
    path('retry/<int:sms_id>/', views.retry_sms, name='retry_sms'),
    path('process-queue/', views.process_sms_queue_manually, name='process_queue'),
    
    # خروجی گزارش
    path('export/excel/', views.export_sms_log_excel, name='export_sms_log_excel'),
    path('export/pdf/', views.export_sms_log_pdf, name='export_sms_log_pdf'),
    
    # مدیریت قالب‌های پیامک
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:template_id>/', views.template_detail, name='template_detail'),
    path('templates/<int:template_id>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:template_id>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:template_id>/set-default/', views.set_template_default, name='set_template_default'),
    path('templates/<int:template_id>/preview/', views.template_preview, name='template_preview'),
    path('templates/<int:template_id>/test/', views.template_test, name='template_test'),
    path('templates/check/', views.template_check, name='template_check'),
    
    # API endpoints
    path('api/customer/search/', views.support_customer_search, name='support_customer_search'),
    path('api/templates/status/', views.get_templates_for_status, name='get_templates_for_status'),
    path('api/templates/marketing/', views.get_marketing_templates, name='get_marketing_templates'),
    path('api/templates/product/', views.get_product_templates, name='get_product_templates'),
] 