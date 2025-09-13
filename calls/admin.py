from django.contrib import admin
from .models import AutomaticCall, CallCustomer, CallLog, CallQueue


@admin.register(CallQueue)
class CallQueueAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'source', 'customer', 'session_id', 'added_by', 'created_at']
    list_filter = ['source', 'created_at']
    search_fields = ['phone_number', 'session_id', 'customer__name']
    readonly_fields = ['created_at']


@admin.register(AutomaticCall)
class AutomaticCallAdmin(admin.ModelAdmin):
    list_display = ['title', 'call_type', 'status', 'scheduled_time', 'created_by', 'total_calls', 'successful_calls']
    list_filter = ['status', 'call_type', 'created_at', 'scheduled_time']
    search_fields = ['title', 'description', 'phone_numbers', 'queue_session_id']
    readonly_fields = ['created_at', 'updated_at', 'total_calls', 'successful_calls', 'failed_calls']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'description', 'call_type', 'priority')
        }),
        ('زمان‌بندی', {
            'fields': ('scheduled_time', 'start_time', 'end_time')
        }),
        ('وضعیت و اختصاص', {
            'fields': ('status', 'created_by', 'assigned_to')
        }),
        ('تنظیمات صف', {
            'fields': ('queue_session_id',)
        }),
        ('تنظیمات Asterisk', {
            'fields': ('asterisk_api_url', 'asterisk_api_key'),
            'classes': ('collapse',)
        }),
        ('تنظیمات تماس', {
            'fields': ('phone_numbers', 'message_template')
        }),
        ('آمار', {
            'fields': ('total_calls', 'successful_calls', 'failed_calls'),
            'classes': ('collapse',)
        }),
        ('اطلاعات سیستمی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CallCustomer)
class CallCustomerAdmin(admin.ModelAdmin):
    list_display = ['call', 'customer', 'phone_number', 'call_time', 'duration', 'result']
    list_filter = ['call__status', 'call_time', 'result']
    search_fields = ['customer__name', 'phone_number', 'notes']


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ['call', 'timestamp', 'event_type', 'message']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['call__title', 'message']
    readonly_fields = ['timestamp']
