from django.urls import path
from . import views, sales_agent_profile_view, sales_main_page_view, customer_profile_views

urlpatterns = [
    path('search/', customer_profile_views.CustomerSearchView.as_view(), name='customer_search'),
    path('create/', customer_profile_views.CustomerCreateView.as_view(), name='customer_create'),
    path('detail/<int:pk>/', customer_profile_views.CustomerDetailView.as_view(), name='customer_detail'),
    path('sales-agent-profile/', sales_agent_profile_view.as_view(), name='sales_agent_profile'),
]