from django.contrib import admin
from .models import CompanyInfo, ProformaInvoice


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


@admin.register(ProformaInvoice)
class ProformaInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'product_name', 'quantity', 'unit', 
                   'total_price', 'issue_date', 'valid_until', 'is_finalized']
    list_filter = ['is_finalized', 'issue_date', 'valid_until', 'unit']
    search_fields = ['invoice_number', 'customer__name', 'product_name']
    readonly_fields = ['invoice_number', 'total_price', 'created_at', 'updated_at']
    date_hierarchy = 'issue_date'
    
    fieldsets = (
        ('اطلاعات پیش فاکتور', {
            'fields': ('invoice_number', 'customer', 'sales_agent', 'company_info')
        }),
        ('اطلاعات محصول', {
            'fields': ('product', 'product_name', 'product_description')
        }),
        ('مشخصات فروش', {
            'fields': ('quantity', 'unit', 'unit_price', 'total_price')
        }),
        ('تاریخ‌ها', {
            'fields': ('issue_date', 'valid_until')
        }),
        ('سایر اطلاعات', {
            'fields': ('notes', 'is_finalized', 'created_at', 'updated_at')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """اگر پیش فاکتور نهایی شده، تمام فیلدها readonly می‌شوند"""
        if obj and obj.is_finalized:
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields
