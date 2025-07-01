from django.urls import path
from . import views

app_name = 'fledger'

urlpatterns = [
    # داشبورد اصلی
    path('', views.fledger_dashboard, name='fledger_dashboard'),
    
    # مدیریت کیف پول‌ها
    path('wallets/', views.wallet_list, name='wallet_list'),
    path('wallets/<int:wallet_id>/', views.wallet_detail, name='wallet_detail'),
    
    # مدیریت تراکنش‌ها
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.create_transaction, name='create_transaction'),
    path('transactions/<int:transaction_id>/edit/', views.edit_transaction, name='edit_transaction'),
    path('transactions/<int:transaction_id>/delete/', views.delete_transaction, name='delete_transaction'),
    path('transactions/<int:transaction_id>/approve/', views.approve_transaction, name='approve_transaction'),
    path('transactions/<int:transaction_id>/reject/', views.reject_transaction, name='reject_transaction'),
    
    # دفتر کل
    path('ledger/', views.ledger_entries, name='ledger_entries'),
    
    # عملیات سیستمی
    path('recalculate-wallets/', views.recalculate_all_wallets, name='recalculate_wallets'),
    path('sync-purchases/', views.sync_purchases_to_ledger, name='sync_purchases'),
    
    # AJAX endpoints
    path('ajax/varedkonandeh/<int:varedkonandeh_id>/', views.ajax_get_varedkonandeh_info, name='ajax_varedkonandeh_info'),
]