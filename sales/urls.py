from django.urls import path
from . import views, sales_agent_profile_view, general_customer_CRUD_page
from .gcCRUDp import call_session_create_view, customer_search_view, customer_profile_view, purchase_register_view, task_create_view

urlpatterns = [
    path('sales-agent-profile/', sales_agent_profile_view.SalesAgentProfileView.as_view, name='sales_agent_profile'),
    path('gccrudp/', general_customer_CRUD_page.general_customer_CRUD_view, name='general_customer_CRUD'),
    path('call/create/<int:customer_id>/', call_session_create_view.call_session_create_view, name='call_session_create'),
    path('task/create/<int:customer_id>/', task_create_view.task_create_view, name='task_create'),
    path('purchase/register/<int:customer_id>/', purchase_register_view.purchase_register_view, name='purchase_register'),
    path('customer/search/', customer_search_view.customer_search_view, name='customer_search'),
    path('customer/profile/<int:customer_id>/', customer_profile_view.customer_profile_view, name='customer_profile'),
]
