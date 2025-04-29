from django.urls import path
from django.views.generic.base import RedirectView
from django.urls import path, include
from .views import (
    general_customer_CRUD_page, 
    sales_agent_login, 
    sales_agent_logout, 
    sales_agent_profile_view,
    mark_notification_read, 
    sales_dashboard_view, 
    pop_notification,
    todo_list_view
) 
from .views.general_customer_CRUD_page import general_customer_CRUD_view, customer_search, change_task_status, get_related_products, predict_next_purchase
from .views.phone_assignment_views import (admin_import_phone_numbers, admin_phone_assignment_list, 
                                        sales_phone_assignment_list, delete_phone_assignment, 
                                        add_customer_from_assignment)


urlpatterns = [    
    path('customer_search/', general_customer_CRUD_page.customer_search, name='customer_search'),
    path('change_status/<int:pk>', general_customer_CRUD_page.change_task_status, name='change_task_status'),
    path('gccrudp/', general_customer_CRUD_page.general_customer_CRUD_view, name='general_customer_CRUD'),
    path('logout/', sales_agent_logout.logout_view, name='logout'),
    path('predict-next-purchase/', general_customer_CRUD_page.predict_next_purchase, name='predict_next_purchase'),
    path('get-related-products/', general_customer_CRUD_page.get_related_products, name='get_related_products'),

    path('profile/', sales_agent_profile_view.sales_agent_profile_view, name='sales_agent_profile'),
    path('customers/', sales_agent_profile_view.customer_list_view, name='customer_list'),
    path('export_customers/', sales_agent_profile_view.export_customers_to_excel, name='export_customers'),
    path('delete-unpaid-purchase/<int:purchase_id>/', sales_agent_profile_view.delete_unpaid_purchase, name='delete_unpaid_purchase'),

    path('notifications/delete/<int:notification_id>/', mark_notification_read.mark_notification_read, name='delete_notification'),
    path('notifications/deleteAll/', mark_notification_read.mark_all_notifications_read, name='delete_all_notification'),

    path('login/', sales_agent_login.sales_agent_login_view, name='sales_agent_login'),

    path('dashboard/', sales_dashboard_view.sales_dashboard_view, name='sales_dashboard'),

    path('get_unread_notifications/', pop_notification.get_unread_notifications, name='get_unread_notifications'),

    path('captcha/', include('captcha.urls')), 

    path('customer/', general_customer_CRUD_view, name='general_customer_CRUD'),
    path('customer/search/', customer_search, name='customer_search'),
    path('task/<int:pk>/change_status/', change_task_status, name='change_task_status'),
    path('customer/get_related_products/', get_related_products, name='get_related_products'),
    path('customer/predict_next_purchase/', predict_next_purchase, name='predict_next_purchase'),
    
    path('phone-assignment/admin/import/', admin_import_phone_numbers, name='admin_import_phone_numbers'),
    path('phone-assignment/admin/list/', admin_phone_assignment_list, name='admin_phone_assignment_list'),
    path('phone-assignment/list/', sales_phone_assignment_list, name='sales_phone_assignment_list'),
    path('phone-assignment/<int:pk>/delete/', delete_phone_assignment, name='delete_phone_assignment'),
    path('phone-assignment/<int:pk>/add-customer/', add_customer_from_assignment, name='add_customer_from_assignment'),

    path('tasks/', todo_list_view.task_dashboard_view, name='task_dashboard'),
    path('tasks/create/', todo_list_view.create_task_view, name='create_task'),
    path('tasks/completed/', todo_list_view.completed_tasks_view, name='completed_tasks'),
    path('tasks/change-status/<int:task_id>/', todo_list_view.change_task_status, name='change_task_status'),

]
