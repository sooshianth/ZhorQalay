from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models.NonBazargahProduct import NonBazargahProduct
from .models.NonBazargahPurchase import NonBazargahPurchase
from .models.Product import Product
from .models.Hazinah import Hazinah
from .models.Invoice import Invoice
from .models.InvoiceItem import InvoiceItem


@admin.register(NonBazargahProduct)
class NonBazargahProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'status')


@admin.register(NonBazargahPurchase)
class NonBazargahPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'product', 'customer', 'unique_sales_agent', 
        'total_weight', 'unit', 'state', 'company_price', 
        'customer_price', 'created_at'
    )
    list_filter = (
        'state', 'unit', 'type', 'buyer_user_type', 
        'vehicle_type', 'created_at', 'updated_at'
    )
    search_fields = (
        'customer__phone_number', 'customer__first_name', 'customer__last_name',
        'buyer_name', 'delivery_receiver_name', 'unique_sales_agent_code',
        'barbary_confidential_number', 'barbary_customer_number'
    )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات اصلی خرید', {
            'fields': (
                'customer', 'product', 'unit', 'state', 'description',
                'unique_sales_agent_code', 'unique_sales_agent'
            )
        }),
        ('اطلاعات مالی', {
            'fields': (
                'company_price', 'customer_price', 'amount_paid', 'total_weight'
            )
        }),
        ('اطلاعات خریدار', {
            'fields': (
                'buyer_name', 'buyer_national_id', 'buyer_user_type',
                'address', 'buyer_postal_code'
            ),
            'classes': ('collapse',)
        }),
        ('اطلاعات تحویل', {
            'fields': (
                'delivery_receiver_name', 'delivery_address', 
                'delivery_postal_code', 'tahvil_phone_number', 'code_melli_tahvil'
            ),
            'classes': ('collapse',)
        }),
        ('اطلاعات باربری و حمل', {
            'fields': (
                'barbary_confidential_number', 'barbary_customer_number',
                'vehicle_type'
            ),
            'classes': ('collapse',)
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'customer', 'product', 'unique_sales_agent'
        )


@admin.register(Hazinah)
class HazinahAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'cost_type_display', 'formatted_amount', 
        'approval_status_colored', 'payment_status_colored', 
        'expense_date', 'created_by', 'created_at'
    )
    list_filter = (
        'cost_type', 'approval_status', 'expense_date', 'created_at',
        'is_recurring', 'priority', 'due_date'
    )
    search_fields = (
        'title', 'description', 'created_by__username', 'approved_by__username'
    )
    readonly_fields = (
        'final_amount', 'created_at', 'updated_at', 'payment_status',
        'total_transactions_amount', 'remaining_amount', 'approval_date'
    )
    list_per_page = 25
    date_hierarchy = 'expense_date'
    
    fieldsets = (
        ('اطلاعات اصلی هزینه', {
            'fields': (
                'title', 'description', 'cost_type', 'amount',
                'tax_amount', 'discount_amount', 'final_amount'
            )
        }),
        ('تاریخ و زمان‌بندی', {
            'fields': ('expense_date', 'due_date', 'created_at', 'updated_at')
        }),
        ('وضعیت تأیید', {
            'fields': (
                'approval_status', 'approved_by', 'approval_date', 
                'approval_notes'
            )
        }),
        ('وضعیت پرداخت', {
            'fields': (
                'payment_status', 'total_transactions_amount', 
                'remaining_amount'
            ),
            'classes': ('collapse',)
        }),
        ('تنظیمات اضافی', {
            'fields': (
                'priority', 'is_recurring', 'recurring_period',
                'attachment', 'created_by'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def cost_type_display(self, obj):
        return obj.get_cost_type_display()
    cost_type_display.short_description = 'نوع هزینه'
    cost_type_display.admin_order_field = 'cost_type'
    
    def formatted_amount(self, obj):
        return format_html('{} ریال', f'{obj.amount:,}')
    formatted_amount.short_description = 'مبلغ'
    formatted_amount.admin_order_field = 'amount'
    
    def approval_status_colored(self, obj):
        color = obj.get_approval_status_display_color()
        colors_map = {
            'warning': '#ffc107',
            'success': '#28a745', 
            'danger': '#dc3545',
            'info': '#17a2b8',
            'secondary': '#6c757d'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors_map.get(color, '#000'), 
            obj.get_approval_status_display()
        )
    approval_status_colored.short_description = 'وضعیت تأیید'
    approval_status_colored.admin_order_field = 'approval_status'
    
    def payment_status_colored(self, obj):
        color = obj.get_payment_status_display_color()
        colors_map = {
            'warning': '#ffc107',
            'success': '#28a745',
            'danger': '#dc3545', 
            'info': '#17a2b8',
            'secondary': '#6c757d'
        }
        status_display = {
            'unpaid': 'پرداخت نشده',
            'paid': 'پرداخت شده',
            'partial': 'پرداخت جزئی',
            'cancelled': 'لغو شده'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors_map.get(color, '#000'),
            status_display.get(obj.payment_status, 'نامشخص')
        )
    payment_status_colored.short_description = 'وضعیت پرداخت'
    
    actions = ['approve_expenses', 'reject_expenses', 'mark_auto_approved']
    
    def approve_expenses(self, request, queryset):
        updated = 0
        for expense in queryset.filter(approval_status='pending'):
            if expense.approve(request.user):
                updated += 1
        self.message_user(request, f'{updated} هزینه تأیید شد.')
    approve_expenses.short_description = 'تأیید هزینه‌های انتخاب شده'
    
    def reject_expenses(self, request, queryset):
        updated = 0
        for expense in queryset.filter(approval_status='pending'):
            if expense.reject(request.user, 'رد شده توسط ادمین'):
                updated += 1
        self.message_user(request, f'{updated} هزینه رد شد.')
    reject_expenses.short_description = 'رد هزینه‌های انتخاب شده'
    
    def mark_auto_approved(self, request, queryset):
        updated = queryset.filter(approval_status='pending').update(
            approval_status='auto_approved',
            approved_by=request.user,
            approval_date=timezone.now()
        )
        self.message_user(request, f'{updated} هزینه به صورت خودکار تأیید شد.')
    mark_auto_approved.short_description = 'تأیید خودکار هزینه‌های انتخاب شده'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'created_by', 'approved_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # اگر ایجاد جدید است
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ('product_type', 'cargo_product', 'non_bazargah_product', 'price', 'amount', 'get_formatted_total_price')
    readonly_fields = ('get_formatted_total_price',)
    
    def get_formatted_total_price(self, obj):
        if obj.pk:  # فقط برای آبجکت‌های ذخیره شده
            return obj.get_formatted_total_price()
        return "0 ریال"
    get_formatted_total_price.short_description = 'قیمت کل'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_id', 'type', 'get_related_object_name', 
        'get_formatted_total_amount', 'get_items_count', 
        'issue_date', 'created_at'
    )
    list_filter = ('type', 'issue_date', 'created_at')
    search_fields = ('invoice_id', 'description', 'hazinah__title', 'income__title')
    readonly_fields = ('get_total_amount', 'get_items_count', 'created_at')
    inlines = [InvoiceItemInline]
    date_hierarchy = 'issue_date'
    list_per_page = 20
    
    fieldsets = (
        ('اطلاعات اصلی فاکتور', {
            'fields': ('invoice_id', 'type', 'description', 'issue_date')
        }),
        ('مرتبط با', {
            'fields': ('hazinah', 'income')
        }),
        ('پیوست‌ها و اطلاعات اضافی', {
            'fields': ('attachment', 'created_at'),
            'classes': ('collapse',)
        }),
        ('خلاصه مالی', {
            'fields': ('get_total_amount', 'get_items_count'),
            'classes': ('collapse',)
        }),
    )
    
    def get_related_object_name(self, obj):
        related = obj.get_related_object()
        if related:
            return str(related)
        return "نامشخص"
    get_related_object_name.short_description = 'مرتبط با'
    
    def get_formatted_total_amount(self, obj):
        total = obj.get_total_amount()
        return format_html('{} ریال', f'{total:,}') if total > 0 else '0 ریال'
    get_formatted_total_amount.short_description = 'مبلغ کل'
    get_formatted_total_amount.admin_order_field = 'get_total_amount'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'hazinah', 'income'
        ).prefetch_related('items')


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = (
        'invoice', 'product_type', 'get_product_name', 
        'formatted_price', 'amount', 'get_formatted_total_price'
    )
    list_filter = ('product_type', 'invoice__type')
    search_fields = (
        'invoice__invoice_id', 'cargo_product__name', 
        'non_bazargah_product__name'
    )
    readonly_fields = ('get_total_price', 'get_formatted_total_price')
    
    fieldsets = (
        ('اطلاعات آیتم', {
            'fields': ('invoice', 'product_type')
        }),
        ('محصول', {
            'fields': ('cargo_product', 'non_bazargah_product')
        }),
        ('قیمت و مقدار', {
            'fields': ('price', 'amount', 'get_total_price', 'get_formatted_total_price')
        }),
    )
    
    def formatted_price(self, obj):
        if obj.price:
            return format_html('{} ریال', f'{obj.price:,}')
        return '0 ریال'
    formatted_price.short_description = 'قیمت واحد'
    formatted_price.admin_order_field = 'price'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'invoice', 'cargo_product', 'non_bazargah_product'
        )


