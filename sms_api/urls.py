from django.urls import path
from . import views

app_name = 'sms_api'

urlpatterns = [
    # صفحات اصلی مدیریت پیامک
    path('dashboard/', views.sms_dashboard, name='sms_dashboard'),
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
] 