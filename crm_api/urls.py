from django.urls import path
from .api import PurchaseInfoAPI, CustomerPurchasesAPI

app_name = 'crm_api'

urlpatterns = [
    # API برای دریافت اطلاعات یک خرید خاص
    path('purchase-info/', PurchaseInfoAPI.as_view(), name='purchase_info'),
    
    # API برای دریافت لیست خریدهای یک مشتری
    path('customer-purchases/', CustomerPurchasesAPI.as_view(), name='customer_purchases'),
]
