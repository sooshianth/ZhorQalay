from django.urls import path
from .api import PurchaseInfoAPI, CustomerPurchasesAPI, PhoneValidationAPI, HealthCheckAPI, CargoProductsAPI, VerifiedPurchasesAPI

app_name = 'crm_api'

urlpatterns = [
    # API برای دریافت اطلاعات یک خرید خاص
    path('purchase-info/', PurchaseInfoAPI.as_view(), name='purchase_info'),
    
    # API برای دریافت لیست خریدهای یک مشتری
    path('customer-purchases/', CustomerPurchasesAPI.as_view(), name='customer_purchases'),
    
    # API برای احراز هویت شماره تلفن
    path('phone-validation/', PhoneValidationAPI.as_view(), name='phone_validation'),
    
    # API برای بررسی سلامت سرویس
    path('health/', HealthCheckAPI.as_view(), name='health_check'),

    # API برای دریافت لیست محصولات فعال بازارگاهی
    path('cargo-products/', CargoProductsAPI.as_view(), name='cargo_products'),
    
    # API برای دریافت خریدهای تایید شده و دارای تخصیص
    path('verified-purchases/', VerifiedPurchasesAPI.as_view(), name='verified_purchases'),
]

