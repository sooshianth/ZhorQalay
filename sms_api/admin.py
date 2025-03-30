from django.contrib import admin
from .models import SmsLog

@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_number', 'sent_at', 'message')
    list_filter = ('sent_at',)
    search_fields = ('recipient_number', 'message')
    readonly_fields = ('sent_at',)
    ordering = ('-sent_at',)
