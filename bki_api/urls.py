from django.urls import path
from . import views

app_name = 'bki_api'

urlpatterns = [
    path('credentials/', views.credentials_view, name='credentials'),
    path('test-kharid-info/', views.test_kharid_info, name='test_kharid_info'),
    path('update-purchase-info/', views.update_purchase_info, name='update_purchase_info'),
    path('bulk-update/', views.bulk_update_purchases, name='bulk_update'),
    path('update-all-purchases/', views.update_all_purchases, name='update_all_purchases'),
    path('get-all-purchases/', views.get_all_bazaargah_purchases_view, name='get_all_purchases'),
    path('merge-purchases/', views.merge_purchases_view, name='merge_purchases'),
] 