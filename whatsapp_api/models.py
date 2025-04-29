from django.db import models
from django.utils import timezone

class WhatsappLog(models.Model):
    recipient_number = models.CharField(max_length=20)
    message = models.TextField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_from = models.ForeignKey('WhatsappNumber', on_delete=models.SET_NULL, null=True, blank=True)
    template_type = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"WhatsApp to {self.recipient_number} at {self.sent_at}"

    class Meta:
        verbose_name = "تاریخچه واتساپ"
        verbose_name_plural = "تاریخچه پیام‌های واتساپ"

class WhatsappNumber(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    daily_limit = models.IntegerField(default=50)
    sent_today = models.IntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=100, blank=True, null=True)
    priority = models.IntegerField(default=1, help_text="اولویت استفاده از این شماره (اعداد کمتر اولویت بالاتر دارند)")
    working_days = models.CharField(
        max_length=13, 
        default="1,2,3,4,5,6,7",
        help_text="روزهای فعال هفته (1-7 که 1=شنبه و 7=جمعه است) به صورت کاما جدا شده"
    )
    chrome_profile = models.CharField(
        max_length=50,
        default='Default',
        help_text="نام پروفایل کروم مربوط به این شماره (مثال: Profile 1, Profile 2)"
    )
    
    def is_available_today(self):
        today = timezone.now().isoweekday()
        return str(today) in self.working_days.split(',')
    
    def can_send_more(self):
        return self.is_active and self.is_available_today() and self.sent_today < self.daily_limit

    def __str__(self):
        return self.phone_number

    class Meta:
        verbose_name = "شماره واتساپ"
        verbose_name_plural = "شماره های واتساپ"


class WhatsappTemplate(models.Model):
    TEMPLATE_TYPES = [
        ('WELCOME', 'پیام خوشامدگویی'),
        ('ORDER_CONFIRM', 'تایید سفارش'),
        ('PAYMENT', 'اطلاع رسانی پرداخت'),
        ('SHIPMENT', 'پیام ارسال مرسوله'),
        ('DELIVERY', 'تحویل سفارش'),
        ('PROMOTION', 'پیام تبلیغاتی'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="نام تمپلیت")
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, verbose_name="نوع تمپلیت")
    content = models.TextField(verbose_name="محتوا")
    variables = models.JSONField(default=dict, verbose_name="متغیرهای قابل استفاده")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    class Meta:
        verbose_name = "تمپلیت واتساپ"
        verbose_name_plural = "تمپلیت‌های واتساپ"
        ordering = ['template_type', 'name']


class WhatsappQueue(models.Model):
    recipient_number = models.CharField(max_length=20)
    template_type = models.CharField(max_length=50)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=[
        ('pending', 'در انتظار ارسال'),
        ('sent', 'ارسال شده'),
        ('failed', 'ناموفق'),
        ('suspended', 'معلق'),
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    # سایر فیلدهای مورد نیاز...

