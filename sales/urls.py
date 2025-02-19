from django.urls import path
from . import views, sales_agent_profile_view, general_customer_CRUD_page, sales_agent_login, sales_agent_logout



urlpatterns = [
    path('gccrudp/', general_customer_CRUD_page.general_customer_CRUD_view, name='general_customer_CRUD'),
    path('profile/', sales_agent_profile_view.sales_agent_profile_view, name='sales_agent_profile'),
    path('customers/', sales_agent_profile_view.customer_list_view, name='customer_list'),
    path('login/', sales_agent_login.sales_agent_login_view, name='sales_agent_login'),
    path('logout/', sales_agent_logout.logout_view, name='logout'),
]
