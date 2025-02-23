from django.urls import path
from django.views.generic.base import RedirectView

from .views import cargo_product_view, general_customer_CRUD_page, sales_agent_login, sales_agent_logout, sales_agent_profile_view, purchase_CRUD_view



urlpatterns = [
    path('', RedirectView.as_view(url='/sales/login/', permanent=False)),  # صفحه پیش‌فرض به لاگین
    path('customer_search/', general_customer_CRUD_page.customer_search, name='customer_search'),
    path('change_status/<int:pk>', general_customer_CRUD_page.change_task_status, name='change_task_status'),
    path('gccrudp/', general_customer_CRUD_page.general_customer_CRUD_view, name='general_customer_CRUD'),
    path('purchase_CRUD/<int:purchase_id>/', purchase_CRUD_view.purchase_CRUD_view, name='purchase_CRUD'),
    path('profile/', sales_agent_profile_view.sales_agent_profile_view, name='sales_agent_profile'),
    path('customers/', sales_agent_profile_view.customer_list_view, name='customer_list'),
    path('login/', sales_agent_login.sales_agent_login_view, name='sales_agent_login'),
    path('cargo_products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('logout/', sales_agent_logout.logout_view, name='logout'),
]
