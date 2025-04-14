from django.db import models
from django.utils import timezone

class SmsQueue(models.Model):
    NOTIFICATION_TYPES = [
        ('new_purchase', 'اطلاع رسانی خرید جدید'),
        ('payment_confirmation', 'تایید پرداخت'),
        ('address_notification', 'اطلاع رسانی آدرس'),
        ('barnameh_notification', 'اطلاع رسانی بارنامه'),
        ('extelaf_notification', 'اطلاع رسانی اختلاف'),
        ('custom', 'پیام سفارشی'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار ارسال'),
        ('sent', 'ارسال شده'),
        ('failed', 'ارسال ناموفق'),
        ('suspended', 'معلق'),
    ]

    recipient_number = models.CharField(max_length=11, verbose_name="شماره گیرنده")
    message = models.TextField(max_length=255, verbose_name="متن پیام")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='custom', verbose_name="نوع اطلاع رسانی")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    is_suspended = models.BooleanField(default=False, verbose_name="معلق شده")
    retry_count = models.IntegerField(default=0, verbose_name="تعداد تلاش مجدد")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    scheduled_for = models.DateTimeField(default=timezone.now, verbose_name="زمان ارسال")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ ارسال")
    
    # Optional reference to purchase if applicable
    purchase_id = models.IntegerField(null=True, blank=True, verbose_name="شناسه خرید")
    
    def __str__(self):
        return f"SMS to {self.recipient_number} - {self.get_status_display()}"

    class Meta:
        verbose_name = "صف پیامک"
        verbose_name_plural = "صف پیامک‌ها"
        ordering = ['scheduled_for', 'created_at']

class SmsLog(models.Model):
    recipient_number = models.CharField(max_length=11, verbose_name="شماره گیرنده")
    message = models.TextField(max_length=255, verbose_name="متن پیام")
    notification_type = models.CharField(max_length=30, null=True, blank=True, verbose_name="نوع اطلاع رسانی")
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")
    status = models.CharField(max_length=10, default='sent', verbose_name="وضعیت")
    api_response = models.TextField(null=True, blank=True, verbose_name="پاسخ API")
    purchase_id = models.IntegerField(null=True, blank=True, verbose_name="شناسه خرید")

    def __str__(self):
        return f"SMS to {self.recipient_number} at {self.sent_at}"

    class Meta:
        verbose_name = "تاریخچه پیامک"
        verbose_name_plural = "تاریخچه پیامک‌ها"
        ordering = ['-sent_at']