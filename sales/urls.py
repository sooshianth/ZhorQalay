from django.urls import path
from django.views.generic.base import RedirectView
from . import views, sales_agent_profile_view, general_customer_CRUD_page, sales_agent_login, sales_agent_logout, cargo_product_view



urlpatterns = [
    path('', RedirectView.as_view(url='/sales/login/', permanent=False)),  # صفحه پیش‌فرض به لاگین
    path('gccrudp/', general_customer_CRUD_page.general_customer_CRUD_view, name='general_customer_CRUD'),
    path('profile/', sales_agent_profile_view.sales_agent_profile_view, name='sales_agent_profile'),
    path('customers/', sales_agent_profile_view.customer_list_view, name='customer_list'),
    path('login/', sales_agent_login.sales_agent_login_view, name='sales_agent_login'),
    path('cargo_products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('logout/', sales_agent_logout.logout_view, name='logout'),
]
