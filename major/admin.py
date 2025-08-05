from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models.NonBazargahProduct import NonBazargahProduct
from .models.Product import Product
from .models.Hazinah import Hazinah


@admin.register(NonBazargahProduct)
class NonBazargahProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'status')


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
        'title', 'description', 'vendor_name', 'vendor_phone',
        'created_by__username', 'approved_by__username'
    )
    readonly_fields = (
        'final_amount', 'created_at', 'updated_at', 'payment_status',
        'total_transactions_amount', 'remaining_amount'
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
        ('محصولات مرتبط', {
            'fields': ('cargo_product', 'non_bazargah_product'),
            'classes': ('collapse',)
        }),
        ('اطلاعات فروشنده', {
            'fields': ('vendor_name', 'vendor_phone', 'vendor_address'),
            'classes': ('collapse',)
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
            'cargo_product', 'non_bazargah_product', 
            'created_by', 'approved_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # اگر ایجاد جدید است
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


