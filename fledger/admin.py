from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Wallet, Transaction, LedgerEntry


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('varedkonandeh', 'formatted_balance', 'transaction_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('varedkonandeh__name', 'description')
    readonly_fields = ('balance', 'created_at', 'updated_at')
    list_per_page = 20
    
    def formatted_balance(self, obj):
        color = 'green' if obj.balance >= 0 else 'red'
        return format_html(
            '<span style="color: {};">{:,} ریال</span>',
            color, obj.balance
        )
    formatted_balance.short_description = 'موجودی'
    formatted_balance.admin_order_field = 'balance'
    
    def transaction_count(self, obj):
        count = obj.transactions.count()
        url = reverse('admin:fledger_transaction_changelist') + f'?wallet__id__exact={obj.id}'
        return format_html('<a href="{}">{} تراکنش</a>', url, count)
    transaction_count.short_description = 'تعداد تراکنش‌ها'
    
    actions = ['recalculate_balance']
    
    def recalculate_balance(self, request, queryset):
        updated = 0
        for wallet in queryset:
            wallet.calculate_balance()
            updated += 1
        self.message_user(request, f'{updated} کیف پول بروزرسانی شد.')
    recalculate_balance.short_description = 'محاسبه مجدد موجودی'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'wallet_name', 'transaction_type', 'formatted_amount', 
        'status', 'created_by', 'approved_by', 'created_at'
    )
    list_filter = ('status', 'transaction_type', 'created_at', 'approved_at')
    search_fields = ('wallet__varedkonandeh__name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('wallet', 'transaction_type', 'amount', 'description')
        }),
        ('فایل و مدارک', {
            'fields': ('file',),
            'classes': ('collapse',)
        }),
        ('وضعیت', {
            'fields': ('status', 'created_by', 'approved_by', 'approved_at')
        }),
        ('زمان‌بندی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def wallet_name(self, obj):
        return obj.wallet.varedkonandeh.name
    wallet_name.short_description = 'واردکننده'
    wallet_name.admin_order_field = 'wallet__varedkonandeh__name'
    
    def formatted_amount(self, obj):
        color = 'green' if obj.transaction_type in ['deposit', 'adjustment'] else 'red'
        return format_html(
            '<span style="color: {};">{:,} ریال</span>',
            color, obj.amount
        )
    formatted_amount.short_description = 'مبلغ'
    formatted_amount.admin_order_field = 'amount'
    
    actions = ['approve_transactions', 'reject_transactions']
    
    def approve_transactions(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        # بروزرسانی کیف پول‌ها
        for transaction in queryset.filter(status='approved'):
            transaction.wallet.calculate_balance()
        self.message_user(request, f'{updated} تراکنش تایید شد.')
    approve_transactions.short_description = 'تایید تراکنش‌های انتخاب شده'
    
    def reject_transactions(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} تراکنش لغو شد.')
    reject_transactions.short_description = 'لغو تراکنش‌های انتخاب شده'


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'varedkonandeh', 'purchase_link', 'weight', 
        'price_per_kg', 'formatted_total_amount', 'wallet_index_used', 'created_at'
    )
    list_filter = ('wallet_index_used', 'created_at', 'varedkonandeh')
    search_fields = (
        'varedkonandeh__name', 'purchase__invoice_id', 
        'purchase__purchase_number', 'notes'
    )
    readonly_fields = ('created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('varedkonandeh', 'purchase')
        }),
        ('جزئیات مالی', {
            'fields': ('weight', 'price_per_kg', 'total_amount', 'wallet_index_used')
        }),
        ('یادداشت‌ها', {
            'fields': ('notes', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def purchase_link(self, obj):
        url = reverse('admin:core_purchase_change', args=[obj.purchase.id])
        return format_html('<a href="{}">{}</a>', url, obj.purchase.invoice_id)
    purchase_link.short_description = 'خرید'
    purchase_link.admin_order_field = 'purchase__invoice_id'
    
    def formatted_total_amount(self, obj):
        return format_html('{:,} ریال', obj.total_amount)
    formatted_total_amount.short_description = 'مبلغ کل'
    formatted_total_amount.admin_order_field = 'total_amount'
    
    actions = ['sync_with_purchase']
    
    def sync_with_purchase(self, request, queryset):
        updated = 0
        for entry in queryset:
            if entry.purchase:
                LedgerEntry.create_or_update_entry(entry.purchase)
                updated += 1
        self.message_user(request, f'{updated} ثبت دفتر همگام‌سازی شد.')
    sync_with_purchase.short_description = 'همگام‌سازی با خرید'


# تنظیمات کلی Admin
admin.site.site_header = "مدیریت کیف پول واردکنندگان"
admin.site.site_title = "Fledger Admin"
admin.site.index_title = "پنل مدیریت"
