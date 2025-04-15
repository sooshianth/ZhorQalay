from django.contrib import admin
from .models import WhatsappNumber, WhatsappLog, WhatsappTemplate

@admin.register(WhatsappNumber)
class WhatsappNumberAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'is_active', 'messages_sent','priority','chrome_profile')

@admin.register(WhatsappLog)
class WhatsappLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_number','sent_at','sent_from')

@admin.register(WhatsappTemplate)
class WhatsappTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'updated_at')
    list_filter = ('template_type', 'is_active')
    search_fields = ('name', 'content')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'template_type', 'is_active')
        }),
        ('محتوا', {
            'fields': ('content', 'variables')
        }),
        ('تاریخچه', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

