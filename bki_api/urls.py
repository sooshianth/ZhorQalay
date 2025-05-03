from django.urls import path
from . import views

app_name = 'bki_api'

urlpatterns = [
    path('credentials/', views.credentials_view, name='credentials'),
    path('test-kharid-info/', views.test_kharid_info, name='test_kharid_info'),
    path('update-purchase-info/', views.update_purchase_info, name='update_purchase_info'),
    path('bulk-update/', views.bulk_update_purchases, name='bulk_update'),
] 