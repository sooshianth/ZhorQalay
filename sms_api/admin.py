from django.contrib import admin
from .models import SmsLog, SmsQueue, SmsTemplate
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

class SmsTemplateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ایجاد دکمه های جایگزین
        placeholder_buttons = ''
        for key, label in SmsTemplate.get_available_placeholders().items():
            button_html = f'<button type="button" class="btn btn-secondary btn-sm placeholder-btn mb-1" data-placeholder="{{{{ {key} }}}}">{label}</button> '
            placeholder_buttons += button_html
            
        # اضافه کردن راهنمای استفاده از دکمه‌ها
        self.fields['content'].help_text = mark_safe(
            f'<div class="alert alert-info">برای اضافه کردن متغیر به متن قالب، روی دکمه‌های زیر کلیک کنید:</div>'
            f'<div class="placeholder-buttons mb-3">{placeholder_buttons}</div>'
            f'<div class="alert alert-warning">نکته: متغیرها با فرمت {{{{ نام_متغیر }}}} در متن قرار می‌گیرند. '
            f'در صورت نبود مقدار، خالی نمایش داده می‌شوند.</div>'
        )
        
    class Meta:
        model = SmsTemplate
        fields = '__all__'
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10, 'class': 'template-content'}),
        }
        
@admin.register(SmsTemplate)
class SmsTemplateAdmin(admin.ModelAdmin):
    form = SmsTemplateForm
    list_display = ('name', 'template_type', 'is_default', 'created_at', 'updated_at')
    list_filter = ('template_type', 'is_default', 'created_at')
    search_fields = ('name', 'content', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'template_type', 'is_default', 'description')
        }),
        ('متن قالب', {
            'fields': ('content',),
            'classes': ('placeholder-editor',),
        }),
    )
    
    class Media:
        css = {
            'all': ('admin/css/sms_template_admin.css',)
        }
        js = ('admin/js/sms_template_admin.js',)
    
    def save_model(self, request, obj, form, change):
        """تضمین می‌کند که هر نوع قالب حداقل یک قالب پیشفرض داشته باشد"""
        super().save_model(request, obj, form, change)
        
        # اگر فقط یک قالب از این نوع وجود دارد، آن را به عنوان پیش‌فرض تنظیم می‌کنیم
        if SmsTemplate.objects.filter(template_type=obj.template_type).count() == 1:
            if not obj.is_default:
                obj.is_default = True
                obj.save()
