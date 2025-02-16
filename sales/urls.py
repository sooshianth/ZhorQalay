from django.urls import path
from . import views, sales_agent_profile_view, sales_main_page_view, customer_profile_views
from .sales_agent_profile_view import customer_list_view, sales_agent_profile

urlpatterns = [
    path('search/', customer_profile_views.CustomerSearchView.as_view(), name='customer_search'),
    path('create/', customer_profile_views.CustomerCreateView.as_view(), name='customer_create'),
    path('detail/<int:pk>/', customer_profile_views.CustomerDetailView.as_view(), name='customer_detail'),
    path('profile/', sales_agent_profile, name='sales_agent_profile'),
    path('customers/', customer_list_view, name='customer_list'),
]