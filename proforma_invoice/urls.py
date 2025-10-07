from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.proforma_list, name='proforma_list'),
    path('create/step1/<int:customer_id>/', views.proforma_step1_customer_info, name='proforma_step1'),
    path('create/step2/<int:customer_id>/', views.proforma_step2_product_selection, name='proforma_step2'),
    path('preview/<int:proforma_id>/', views.proforma_preview, name='proforma_preview'),
    path('download/<int:proforma_id>/', views.proforma_download_pdf, name='proforma_download_pdf'),
    path('financial-dashboard/', views.financial_dashboard, name='financial_dashboard'),
    path('api/customer-search/', views.customer_search_api, name='customer_search_api'),
    
    # ارسال به مشتری
    path('send-sms/<int:proforma_id>/', views.send_sms_popup, name='send_sms_popup'),
    
    # API endpoints برای KunQalay
    path('api/poll-pending-deliveries/', views.api_poll_pending_deliveries, name='api_poll_pending_deliveries'),
    path('api/confirm-delivery/', views.api_confirm_delivery, name='api_confirm_delivery'),
    path('api/queue-proforma-sms/', views.api_queue_proforma_sms, name='api_queue_proforma_sms'),
]

