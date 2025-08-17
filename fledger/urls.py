from django.urls import path
from . import views

app_name = 'fledger'

urlpatterns = [
    # داشبورد اصلی
    path('', views.fledger_dashboard, name='fledger_dashboard'),
    
    # مدیریت کیف پول واردکنندگان
    path('varedkonandeh-wallets/', views.varedkonandeh_wallet_list, name='varedkonandeh_wallet_list'),
    path('varedkonandeh-wallets/<int:wallet_id>/', views.varedkonandeh_wallet_detail, name='varedkonandeh_wallet_detail'),
    
    # مدیریت کیف پول مشتریان
    path('customer-wallets/', views.customer_wallet_list, name='customer_wallet_list'),
    path('customer-wallets/<int:wallet_id>/', views.customer_wallet_detail, name='customer_wallet_detail'),
    
    # مدیریت کیف پول‌ها (عمومی - برای backward compatibility)
    path('wallets/', views.wallet_list, name='wallet_list'),
    path('wallets/<int:wallet_id>/', views.wallet_detail, name='wallet_detail'),
    
    # مدیریت تراکنش‌ها
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.create_transaction, name='create_transaction'),
    path('transactions/<int:transaction_id>/edit/', views.edit_transaction, name='edit_transaction'),
    path('transactions/<int:transaction_id>/delete/', views.delete_transaction, name='delete_transaction'),
    path('transactions/<int:transaction_id>/approve/', views.approve_transaction, name='approve_transaction'),
    path('transactions/<int:transaction_id>/reject/', views.reject_transaction, name='reject_transaction'),
    
    # مدیریت هزینه‌ها
    path('hazinah/', views.hazinah_list, name='hazinah_list'),
    path('hazinah/create/', views.create_hazinah, name='create_hazinah'),
    path('hazinah/<int:hazinah_id>/', views.hazinah_detail, name='hazinah_detail'),
    path('hazinah/<int:hazinah_id>/edit/', views.edit_hazinah, name='edit_hazinah'),
    path('hazinah/<int:hazinah_id>/approve/', views.approve_hazinah, name='approve_hazinah'),
    path('hazinah/<int:hazinah_id>/reject/', views.reject_hazinah, name='reject_hazinah'),
    path('hazinah/<int:hazinah_id>/pay/', views.pay_hazinah, name='pay_hazinah'),
    path('hazinah/<int:hazinah_id>/delete/', views.delete_hazinah, name='delete_hazinah'),
    
    # مدیریت فاکتورهای هزینه
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.create_invoice, name='create_invoice'),
    path('invoices/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('hazinah/<int:hazinah_id>/invoice/add/', views.add_invoice_to_hazinah, name='add_invoice_to_hazinah'),
    path('hazinah/<int:hazinah_id>/invoice/<int:invoice_id>/edit/', views.edit_invoice, name='edit_invoice'),
    path('hazinah/<int:hazinah_id>/invoice/<int:invoice_id>/delete/', views.delete_invoice, name='delete_invoice'),
    
    # دفتر کل
    path('ledger/', views.ledger_entries, name='ledger_entries'),
    
    # عملیات سیستمی
    path('recalculate-wallets/', views.recalculate_all_wallets, name='recalculate_wallets'),
    path('sync-purchases/', views.sync_purchases_to_ledger, name='sync_purchases'),
    
    # داشبورد لجستیک
    path('logistics/', views.logistics_dashboard, name='logistics_dashboard'),
    
    # AJAX endpoints
    path('ajax/varedkonandeh/<int:varedkonandeh_id>/', views.ajax_get_varedkonandeh_info, name='ajax_varedkonandeh_info'),
]