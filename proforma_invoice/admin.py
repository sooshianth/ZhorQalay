from django.contrib import admin
from .models import CompanyInfo, ProformaInvoice, ProformaInvoiceItem, ProformaInvoiceDelivery


@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'phone_number', 'email', 'is_active', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['company_name', 'company_id_code', 'phone_number', 'email']
    
    fieldsets = (
        ('اطلاعات شناسایی', {
            'fields': ('company_name', 'company_id_code', 'economic_code', 'registration_number')
        }),
        ('اطلاعات تماس', {
            'fields': ('phone_number', 'mobile_number', 'email', 'website')
        }),
        ('آدرس و موقعیت', {
            'fields': ('address', 'postal_code')
        }),
        ('اطلاعات مالی', {
            'fields': ('bank_name', 'account_number', 'iban', 'card_number')
        }),
        ('تصاویر', {
            'fields': ('logo', 'signature_image')
        }),
        ('ملاحظات و تنظیمات', {
            'fields': ('default_notes', 'is_active')
        }),
    )


class ProformaInvoiceItemInline(admin.TabularInline):
    model = ProformaInvoiceItem
    extra = 1
    fields = ['product_name', 'product_description', 'quantity', 'unit', 'unit_price', 'order']


@admin.register(ProformaInvoice)
class ProformaInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'total_price', 'issue_date', 'valid_until', 'is_finalized']
    list_filter = ['is_finalized', 'issue_date', 'valid_until']
    search_fields = ['invoice_number', 'customer__name']
    readonly_fields = ['invoice_number', 'total_price', 'created_at', 'updated_at']
    date_hierarchy = 'issue_date'
    inlines = [ProformaInvoiceItemInline]
    
    fieldsets = (
        ('اطلاعات پیش فاکتور', {
            'fields': ('invoice_number', 'customer', 'sales_agent', 'company_info')
        }),
        ('تاریخ‌ها', {
            'fields': ('issue_date', 'valid_until')
        }),
        ('سایر اطلاعات', {
            'fields': ('total_price', 'notes', 'is_finalized', 'created_at', 'updated_at')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """اگر پیش فاکتور نهایی شده، تمام فیلدها readonly می‌شوند"""
        if obj and obj.is_finalized:
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields


@admin.register(ProformaInvoiceItem)
class ProformaInvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['proforma', 'product_name', 'quantity', 'unit', 'unit_price', 'order']
    list_filter = ['unit', 'proforma__issue_date']
    search_fields = ['product_name', 'proforma__invoice_number']


@admin.register(ProformaInvoiceDelivery)
class ProformaInvoiceDeliveryAdmin(admin.ModelAdmin):
    list_display = ['proforma', 'status', 'sent_by', 'created_at', 'sent_at']
    list_filter = ['status', 'created_at', 'sent_at']
    search_fields = ['proforma__invoice_number', 'proforma__customer__name', 'notes']
    readonly_fields = ['created_at', 'sent_at', 'downloaded_at']
    
    fieldsets = (
        ('اطلاعات پیش‌فاکتور', {
            'fields': ('proforma', 'sent_by')
        }),
        ('شماره‌های تلفن', {
            'fields': ('phone_numbers',)
        }),
        ('وضعیت', {
            'fields': ('status',)
        }),
        ('زمان‌بندی', {
            'fields': ('created_at', 'sent_at', 'downloaded_at')
        }),
        ('یادداشت', {
            'fields': ('notes',)
        }),
    )
