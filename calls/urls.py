from django.urls import path
from . import views

app_name = 'calls'

urlpatterns = [
    # داشبورد تماس‌های اتوماتیک
    path('', views.automatic_calls_dashboard, name='automatic_calls_dashboard'),
    path('dashboard/', views.automatic_calls_dashboard, name='dashboard'),
    
    # مدیریت تماس‌های اتوماتیک
    path('automatic/', views.automatic_calls_list, name='automatic_calls_list'),
    path('automatic/create/', views.create_automatic_call, name='create_automatic_call'),
    path('automatic/<int:call_id>/', views.automatic_call_detail, name='automatic_call_detail'),
    path('automatic/<int:call_id>/edit/', views.edit_automatic_call, name='edit_automatic_call'),
    path('automatic/<int:call_id>/stop/', views.stop_automatic_call, name='stop_automatic_call'),
    path('automatic/<int:call_id>/delete/', views.delete_automatic_call, name='delete_automatic_call'),
    path('automatic/<int:call_id>/start-asterisk/', views.start_asterisk_call, name='start_asterisk_call'),
    
    # Queue Management API endpoints
    path('api/queue/add-customer/', views.add_customer_to_queue, name='add_customer_to_queue'),
    path('api/queue/add-manual/', views.add_manual_numbers_to_queue, name='add_manual_numbers_to_queue'),
    path('api/queue/upload-excel/', views.upload_excel_to_queue, name='upload_excel_to_queue'),
    path('api/queue/add-suggestions/', views.add_suggested_numbers_to_queue, name='add_suggested_numbers_to_queue'),
    path('api/queue/remove/', views.remove_from_queue, name='remove_from_queue'),
    path('api/queue/get-numbers/', views.get_queue_numbers, name='get_queue_numbers'),
    path('api/customers/search/', views.search_customers_api, name='search_customers_api'),
    
    # API endpoints
    path('api/stats/', views.get_call_stats_api, name='get_call_stats_api'),
]
