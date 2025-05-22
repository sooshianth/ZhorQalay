from django.urls import path
from . import views

app_name = 'bki_api'

urlpatterns = [
    path('credentials/', views.credentials_view, name='credentials'),
    path('test-kharid-info/', views.test_kharid_info, name='test_kharid_info'),
    path('update-purchase-info/', views.update_purchase_info, name='update_purchase_info'),  # Solo para pruebas
    path('bulk-update/', views.bulk_update_purchases, name='bulk_update'),  # Solo para pruebas
    path('update-all-purchases/', views.update_all_purchases, name='update_all_purchases'),
    path('get-all-purchases/', views.get_all_bazaargah_purchases_view, name='get_all_purchases'),
    path('merge-purchases/', views.merge_purchases_view, name='merge_purchases'),
    path('get-purchases-last-day/', views.get_purchases_last_day_view, name='get_purchases_last_day'),
    path('get-purchases-last-week/', views.get_purchases_last_week_view, name='get_purchases_last_week'),
] 