from django.urls import path, include
from django.views.generic.base import RedirectView

# Core views
from .views import (
    sales_agent_login,
    sales_agent_logout,
    sales_agent_profile_view,
    mark_notification_read,
    sales_dashboard_view,
    pop_notification,
)

# Customer and CRUD views
from .views.general_customer_CRUD_page import (
    general_customer_CRUD_view,
    customer_search,
    change_task_status,
    get_related_products,
    predict_next_purchase
)

# Phone assignment views
from .views.phone_assignment_views import (
    admin_import_phone_numbers,
    admin_phone_assignment_list,
    sales_phone_assignment_list,
    delete_phone_assignment,
    add_customer_from_assignment
)

# Customer list views
from .views.customer_list_view import (
    enhanced_customer_list_view,
    toggle_favorite,
    get_sms_templates,
    send_sms_to_selected,
    get_active_products
)

# Todo list views
from .views import todo_list_view

# Sales agent purchases view

urlpatterns = [
    # Profile and dashboard
    path('profile/', sales_agent_profile_view.sales_agent_profile_view, name='sales_agent_profile'),
    path('dashboard/', sales_dashboard_view.sales_dashboard_view, name='sales_dashboard'),
    path('login/', sales_agent_login.sales_agent_login_view, name='sales_agent_login'),
    path('logout/', sales_agent_logout.logout_view, name='logout'),
    
    # Customer list and management
    path('customers/', RedirectView.as_view(pattern_name='enhanced_customer_list', permanent=False), name='customer_list'),
    path('customers/enhanced/', enhanced_customer_list_view, name='enhanced_customer_list'),
    path('customers/toggle-favorite/', toggle_favorite, name='toggle_favorite'),
    path('customers/send-sms/', send_sms_to_selected, name='send_sms_to_selected'),
    path('customers/get-sms-templates/', get_sms_templates, name='get_sms_templates'),
    
    # Customer CRUD endpoints
    path('customer/', general_customer_CRUD_view, name='general_customer_CRUD'),
    path('customer/search/', customer_search, name='customer_search'),
    path('gccrudp/', general_customer_CRUD_view, name='general_customer_CRUD'),
    path('task/<int:pk>/change_status/', change_task_status, name='change_task_status_todo'),
    path('change_status/<int:pk>', change_task_status, name='change_task_status'),
    path('predict-next-purchase/', predict_next_purchase, name='predict_next_purchase'),
    path('get-related-products/', get_related_products, name='get_related_products'),
    path('customer/get_related_products/', get_related_products, name='get_related_products'),
    path('customer/predict_next_purchase/', predict_next_purchase, name='predict_next_purchase'),
    path('delete-unpaid-purchase/<int:purchase_id>/', sales_agent_profile_view.delete_unpaid_purchase, name='delete_unpaid_purchase'),
    
    # Notification endpoints
    path('notifications/delete/<int:notification_id>/', mark_notification_read.mark_notification_read, name='delete_notification'),
    path('notifications/deleteAll/', mark_notification_read.mark_all_notifications_read, name='delete_all_notification'),
    path('get_unread_notifications/', pop_notification.get_unread_notifications, name='get_unread_notifications'),
    
    # Phone assignment endpoints
    path('phone-assignment/admin/import/', admin_import_phone_numbers, name='admin_import_phone_numbers'),
    path('phone-assignment/admin/list/', admin_phone_assignment_list, name='admin_phone_assignment_list'),
    path('phone-assignment/list/', sales_phone_assignment_list, name='sales_phone_assignment_list'),
    path('phone-assignment/<int:pk>/delete/', delete_phone_assignment, name='delete_phone_assignment'),
    path('phone-assignment/<int:pk>/add-customer/', add_customer_from_assignment, name='add_customer_from_assignment'),
    
    # Todo list endpoints
    path('todos/', todo_list_view.todo_dashboard_view, name='todo_dashboard'),
    path('todos/create/', todo_list_view.create_todo_view, name='create_todo'),
    path('todos/completed/', todo_list_view.completed_todos_view, name='completed_todos'),
    path('todos/change-status/<int:task_id>/', todo_list_view.change_todo_status, name='change_todo_status'),
    path('todos/toggle-status/', todo_list_view.toggle_todo_status, name='toggle_todo_status'),
    path('todos/list/', todo_list_view.todo_list_view, name='todo_list'),
    path('todos/<int:task_id>/', todo_list_view.todo_detail_view, name='todo_detail'),
    path('todos/<int:task_id>/edit/', todo_list_view.edit_todo_view, name='edit_todo'),
    path('todos/search/', todo_list_view.search_todos, name='search_todos'),
    path('todos/analytics/', todo_list_view.todo_analytics_view, name='todo_analytics'),
    path('todos/categories/', todo_list_view.manage_categories_view, name='manage_categories'),
    
    # Sales purchases view
    
    # API endpoints
    path('api/active-products/', get_active_products, name='get_active_products'),
    
    # External apps
    path('captcha/', include('captcha.urls')),
]
