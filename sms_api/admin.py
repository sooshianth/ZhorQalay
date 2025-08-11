from django.contrib import admin
from .models import SmsLog, SmsQueue, SmsTemplate, SmsConfig
from .apis import process_sms_queue
from django.utils import timezone
from django import forms
from django.utils.safestring import mark_safe
from django.forms import widgets

@admin.register(SmsQueue)
class SmsQueueAdmin(admin.ModelAdmin):
    list_display = ('recipient_number', 'notification_type', 'status', 'is_suspended', 'created_at', 'scheduled_for', 'sent_at', 'get_purchase_info')
    list_filter = ('status', 'notification_type', 'is_suspended', 'created_at')
    search_fields = ('recipient_number', 'message', 'purchase__purchase_number', 'purchase__invoice_id')
    readonly_fields = ('created_at', 'sent_at')
    raw_id_fields = ('purchase',)
    actions = ['process_selected_sms', 'suspend_selected_sms', 'unsuspend_selected_sms']
    
    def get_purchase_info(self, obj):
        if obj.purchase:
            return f"{obj.purchase.invoice_id} (#{obj.purchase.id})"
        return "-"
    get_purchase_info.short_description = "خرید مرتبط"
    
    def process_selected_sms(self, request, queryset):
        count = queryset.count()
        
        # Only process messages that are pending and not suspended
        valid_queryset = queryset.filter(status='pending', is_suspended=False)
        valid_count = valid_queryset.count()
        
        if valid_count > 0:
            results = []
            for sms in valid_queryset:
                # Mark the SMS for immediate processing
                sms.scheduled_for = timezone.now()
                sms.save()
            
            # Process the queue
            process_results = process_sms_queue(batch_size=valid_count)
            results.extend(process_results)
            
            self.message_user(request, f'{valid_count} پیامک با موفقیت پردازش شد.')
        else:
            skipped = count - valid_count
            self.message_user(request, f'هیچ پیامکی پردازش نشد. {skipped} پیامک رد شد زیرا معلق یا در وضعیت غیر انتظار بودند.')
    process_selected_sms.short_description = "ارسال پیامک‌های انتخاب شده"
    
    def suspend_selected_sms(self, request, queryset):
        # Only suspend messages that are pending
        pending_queryset = queryset.filter(status='pending')
        count = pending_queryset.update(status='suspended', is_suspended=True)
        if count == 1:
            message = 'یک پیامک معلق شد'
        else:
            message = f'{count} پیامک معلق شد'
        self.message_user(request, message)
    suspend_selected_sms.short_description = "معلق کردن پیامک‌های انتخاب شده"
    
    def unsuspend_selected_sms(self, request, queryset):
        # Only unsuspend messages that are suspended
        suspended_queryset = queryset.filter(is_suspended=True)
        count = suspended_queryset.update(status='pending', is_suspended=False)
        if count == 1:
            message = 'یک پیامک از تعلیق خارج شد'
        else:
            message = f'{count} پیامک از تعلیق خارج شد'
        self.message_user(request, message)
    unsuspend_selected_sms.short_description = "خروج پیامک‌های انتخاب شده از تعلیق"

@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_number', 'notification_type', 'status', 'sent_at', 'get_purchase_info')
    list_filter = ('notification_type', 'sent_at', 'status')
    search_fields = ('recipient_number', 'message', 'purchase__purchase_number', 'purchase__invoice_id')
    readonly_fields = ('sent_at', 'recipient_number', 'message', 'notification_type', 'status', 'api_response', 'purchase')
    
    def get_purchase_info(self, obj):
        if obj.purchase:
            return f"{obj.purchase.invoice_id} (#{obj.purchase.id})"
        return "-"
    get_purchase_info.short_description = "خرید مرتبط"

@admin.register(SmsTemplate)
class SmsTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('name', 'content')


@admin.register(SmsConfig)
class SmsConfigAdmin(admin.ModelAdmin):
    list_display = ('sms_enabled',)
    list_filter = ('sms_enabled',)
    search_fields = ('sms_enabled',)
    def has_add_permission(self, request):
        if SmsConfig.objects.exists():
            return False
        return True
    def has_change_permission(self, request, obj=None):
        return True
