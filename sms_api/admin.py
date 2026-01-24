from django.contrib import admin
from .models import SmsLog, SmsQueue, SmsTemplate, SmsConfig, BulkSmsCampaign, BulkSmsNumber
from .apis import process_sms_queue, schedule_bulk_sms_campaign, pause_bulk_sms_campaign, resume_bulk_sms_campaign
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
    list_display = ('sms_enabled', 'purchase_aware_enabled', 'assume_success_on_no_error')
    list_filter = ('sms_enabled', 'purchase_aware_enabled', 'assume_success_on_no_error')
    fieldsets = (
        ('تنظیمات اصلی', {
            'fields': ('sms_enabled',)
        }),
        ('تنظیمات پیشرفته', {
            'fields': ('assume_success_on_no_error',)
        }),
        ('اطلاع‌رسانی خرید جدید', {
            'fields': ('purchase_aware_enabled',),
            'description': 'این بخش مربوط به ارسال پیامک اطلاع‌رسانی خرید جدید به شماره‌های مدیریت است. شماره‌ها در فایل .env تحت عنوان PURCHASE_AWARE_NUMBERS تعریف می‌شوند.'
        }),
    )
    def has_add_permission(self, request):
        if SmsConfig.objects.exists():
            return False
        return True
    def has_change_permission(self, request, obj=None):
        return True

class BulkSmsNumberInline(admin.TabularInline):
    model = BulkSmsNumber
    extra = 0
    readonly_fields = ('phone_number', 'batch_number', 'scheduled_time', 'sms_queue')
    fields = ('phone_number', 'batch_number', 'scheduled_time', 'sms_queue')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(BulkSmsCampaign)
class BulkSmsCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'total_numbers', 'sent_count', 'failed_count', 'progress_percentage', 'created_at', 'start_time')
    list_filter = ('status', 'created_at', 'start_time')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'sent_count', 'failed_count', 'progress_percentage')
    inlines = [BulkSmsNumberInline]
    actions = ['schedule_campaigns', 'pause_campaigns', 'resume_campaigns']
    
    fieldsets = (
        ('اطلاعات کمپین', {
            'fields': ('name', 'description', 'status', 'created_by')
        }),
        ('تنظیمات زمان‌بندی', {
            'fields': ('batch_size', 'batch_interval_minutes', 'start_time')
        }),
        ('متن پیامک', {
            'fields': ('message',)
        }),
        ('آمار', {
            'fields': ('total_numbers', 'sent_count', 'failed_count'),
            'classes': ('collapse',)
        }),
        ('تاریخ و زمان', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def progress_percentage(self, obj):
        return f"{obj.progress_percentage}%"
    progress_percentage.short_description = "پیشرفت"
    
    def schedule_campaigns(self, request, queryset):
        scheduled_count = 0
        failed_count = 0
        
        for campaign in queryset:
            if campaign.status in ['draft', 'scheduled']:
                result = schedule_bulk_sms_campaign(campaign.id)
                if result['success']:
                    scheduled_count += 1
                else:
                    failed_count += 1
        
        if scheduled_count > 0:
            self.message_user(request, f'{scheduled_count} کمپین با موفقیت زمان‌بندی شد.')
        if failed_count > 0:
            self.message_user(request, f'{failed_count} کمپین در زمان‌بندی با خطا مواجه شد.', level='ERROR')
    
    schedule_campaigns.short_description = "شروع کمپین‌های انتخاب شده"
    
    def pause_campaigns(self, request, queryset):
        paused_count = 0
        
        for campaign in queryset:
            if campaign.status in ['scheduled', 'in_progress']:
                success = pause_bulk_sms_campaign(campaign.id)
                if success:
                    paused_count += 1
        
        if paused_count > 0:
            self.message_user(request, f'{paused_count} کمپین با موفقیت متوقف شد.')
        else:
            self.message_user(request, 'هیچ کمپینی متوقف نشد.')
    
    pause_campaigns.short_description = "توقف کمپین‌های انتخاب شده"
    
    def resume_campaigns(self, request, queryset):
        resumed_count = 0
        
        for campaign in queryset:
            if campaign.status == 'paused':
                success = resume_bulk_sms_campaign(campaign.id)
                if success:
                    resumed_count += 1
        
        if resumed_count > 0:
            self.message_user(request, f'{resumed_count} کمپین با موفقیت ادامه یافت.')
        else:
            self.message_user(request, 'هیچ کمپینی ادامه نیافت.')
    
    resume_campaigns.short_description = "ادامه کمپین‌های انتخاب شده"

@admin.register(BulkSmsNumber)
class BulkSmsNumberAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'get_campaign_name', 'batch_number', 'scheduled_time', 'get_sms_status')
    list_filter = ('campaign__status', 'batch_number', 'scheduled_time', 'sms_queue__status')
    search_fields = ('phone_number', 'campaign__name')
    readonly_fields = ('campaign', 'phone_number', 'batch_number', 'scheduled_time', 'sms_queue')
    raw_id_fields = ('campaign', 'sms_queue')
    
    def get_campaign_name(self, obj):
        return obj.campaign.name
    get_campaign_name.short_description = "کمپین"
    
    def get_sms_status(self, obj):
        if obj.sms_queue:
            return obj.sms_queue.get_status_display()
        return "زمان‌بندی نشده"
    get_sms_status.short_description = "وضعیت پیامک"
    
    def has_add_permission(self, request):
        return False  # شماره‌ها فقط از طریق کمپین اضافه می‌شوند
