from django.urls import path
from django.views.generic.base import RedirectView
from django.urls import path, include
from .views import cargo_product_view, general_customer_CRUD_page, sales_agent_login, sales_agent_logout, sales_agent_profile_view
from .views import mark_notification_read, sales_dashboard_view, pop_notification, chatBot_view


urlpatterns = [
    path('', RedirectView.as_view(url='/sales/login/', permanent=False)),  # صفحه پیش‌فرض به لاگین
    path('customer_search/', general_customer_CRUD_page.customer_search, name='customer_search'),
    path('change_status/<int:pk>', general_customer_CRUD_page.change_task_status, name='change_task_status'),
    path('gccrudp/', general_customer_CRUD_page.general_customer_CRUD_view, name='general_customer_CRUD'),
    path('profile/', sales_agent_profile_view.sales_agent_profile_view, name='sales_agent_profile'),
    path('customers/', sales_agent_profile_view.customer_list_view, name='customer_list'),
    path('login/', sales_agent_login.sales_agent_login_view, name='sales_agent_login'),
    path('cargo_products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('logout/', sales_agent_logout.logout_view, name='logout'),
    path('get-related-products/', general_customer_CRUD_page.get_related_products, name='get_related_products'),
    path('dashboard/', sales_dashboard_view.sales_dashboard_view, name='sales_dashboard'),
    path('export_customers/', sales_agent_profile_view.export_customers_to_excel, name='export_customers'),
    path('predict-next-purchase/', general_customer_CRUD_page.predict_next_purchase, name='predict_next_purchase'),
    path('notifications/delete/<int:notification_id>/', mark_notification_read.mark_notification_read, name='delete_notification'),
    path('notifications/deleteAll/', mark_notification_read.mark_all_notifications_read, name='delete_all_notification'),
    path('get_unread_notifications/', pop_notification.get_unread_notifications, name='get_unread_notifications'),
    path('api/users/', chatBot_view.user_list, name='user_list'),
    path('api/chat/history/<int:user_id>/', chatBot_view.chat_history, name='chat_history'),
    path('api/chat/upload/', chatBot_view.upload_file, name='upload_file'),
    path('captcha/', include('captcha.urls')), 
]
