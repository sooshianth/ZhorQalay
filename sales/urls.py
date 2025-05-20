from django.urls import path, include
from django.views.generic.base import RedirectView

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
    predict_next_purchase,
    update_task_order
)

# Phone assignment views
from .views.phone_assignment_views import (
    admin_import_phone_numbers,
    admin_phone_assignment_list,
    sales_phone_assignment_list,
    delete_phone_assignment,
    add_customer_from_assignment,
    update_phone_notes
)

# Customer list views
from .views.customer_list_view import (
    enhanced_customer_list_view,
    toggle_favorite,
    get_sms_templates,
    send_sms_to_selected,
    get_active_products
)

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
    path('task/update-order/', update_task_order, name='update_task_order'),
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
    path('phone-assignment/<int:pk>/update-notes/', update_phone_notes, name='update_phone_notes'),
    
    # Sales purchases view
    
    # API endpoints
    path('api/active-products/', get_active_products, name='get_active_products'),
    
    # External apps
    path('captcha/', include('captcha.urls')),
]
