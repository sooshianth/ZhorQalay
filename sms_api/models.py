from django.db import models
from django.utils import timezone
from django_jalali.db import models as jmodels
from core.PurchaseModel import Purchase

is_celery_active = False

class SmsQueue(models.Model):
    NOTIFICATION_TYPES = [
        # وضعیت‌های خرید
        ('INITIATED', 'شروع شده'),
        ('SMS_SENT', 'پیامک ارسال شده'),
        ('PAYMENT_VERIFIED', 'ثبت خرید در بازارگاه'),
        ('ALLOCATION_APPROVED', 'ثبت تخصیص در بازارگاه'),
        ('ADDRESS_SENT', 'ارسال آدرس به واردکننده'),
        ('WAITING_FOR_BARNAMEH', 'در انتظار بارنامه'),
        ('BARNAMEH_INCOMPLETE', 'صدور بارنامه (ناقص)'),
        ('BARNAMEH_ISSUED', 'صدور بارنامه'),
        ('PURCHASE_CLOSED', 'بستن خرید در بازارگاه'),
        ('PAY_KASRI', 'پرداخت کسری'),
        ('RECIEIVE_SARAK', 'دریافت سرک'),
        ('FULLY_SETTLED', 'تسویه کامل'),
        ('INVOICE_ISSUED', 'صدور فاکتور'),
        ('CANCELED', 'لغو شده'),
        ('ARCHIVED', 'آرشیو شده'),
        # نوع‌های قدیمی برای سازگاری
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
    message = models.TextField(max_length=4800, verbose_name="متن پیام")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='custom', verbose_name="نوع اطلاع رسانی")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    is_suspended = models.BooleanField(default=False, verbose_name="معلق شده")
    retry_count = models.IntegerField(default=0, verbose_name="تعداد تلاش مجدد")
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    scheduled_for = jmodels.jDateTimeField(default=timezone.now, verbose_name="زمان ارسال")
    sent_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name="تاریخ ارسال")

    # رفرنس به خرید - از نام مدل به صورت رشته استفاده می‌کنیم تا از ایمپورت دایره‌ای جلوگیری شود
    purchase = models.ForeignKey('core.Purchase', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="خرید")

    def __str__(self):
        return f"SMS to {self.recipient_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # اگر فقط purchase_id وارد شده باشد و purchase خالی باشد، سعی کنیم purchase را پیدا کنیم
        if self.purchase_id is not None and self.purchase is None:
            try:
                # از importlib استفاده کنیم به جای ایمپورت مستقیم
                from core.PurchaseModel import Purchase
                self.purchase = Purchase.objects.get(pk=self.purchase_id)
            except:
                pass
        
        # اگر purchase وارد شده باشد و purchase_id خالی باشد، purchase_id را از purchase استخراج کنیم
        if self.purchase is not None and self.purchase_id is None:
            self.purchase_id = self.purchase.id
            
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "صف پیامک"
        verbose_name_plural = "صف پیامک‌ها"
        ordering = ['scheduled_for', 'created_at']

class SmsLog(models.Model):
    recipient_number = models.CharField(max_length=11, verbose_name="شماره گیرنده")
    message = models.TextField(max_length=4800, verbose_name="متن پیام")
    notification_type = models.CharField(max_length=30, null=True, blank=True, verbose_name="نوع اطلاع رسانی")
    sent_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")
    status = models.CharField(max_length=10, default='sent', verbose_name="وضعیت")
    api_response = models.TextField(null=True, blank=True, verbose_name="پاسخ API")
    
    # رفرنس به خرید - از نام مدل به صورت رشته استفاده می‌کنیم تا از ایمپورت دایره‌ای جلوگیری شود
    purchase = models.ForeignKey('core.Purchase', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="خرید")

    def __str__(self):
        return f"SMS to {self.recipient_number} at {self.sent_at}"

    class Meta:
        verbose_name = "تاریخچه پیامک"
        verbose_name_plural = "تاریخچه پیامک‌ها"
        ordering = ['-sent_at']

class SmsTemplate(models.Model):
    TEMPLATE_TYPE_CHOICES = [
        ('purchase', 'مربوط به خرید'),
        ('marketing', 'تبلیغاتی'),
        ('product', 'ارسال محصولات'),
    ]
    
    STATUS_CHOICES = Purchase.STATUS_CHOICES
    
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPE_CHOICES, default='purchase', verbose_name="نوع قالب")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, null=True, blank=True, verbose_name="بعد از چه وضعیتی ارسال شود؟")
    name = models.CharField(max_length=100, verbose_name="نام قالب")
    content = models.TextField(verbose_name="متن قالب")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_default = models.BooleanField(default=False, verbose_name="پیش‌فرض")  
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")
    is_for_salesmen = models.BooleanField(default=False, verbose_name="برای کارشناس فروش")

    def __str__(self):
        if self.template_type == 'purchase' and self.status:
            return f"{self.name} ({self.get_status_display()})"
        else:
            return f"{self.name} ({self.get_template_type_display()})"
        
    class Meta:
        verbose_name = "قالب پیامک"
        verbose_name_plural = "قالب‌های پیامک"
        ordering = ['-created_at']
        
    @staticmethod
    def get_available_placeholders():
        """
        دریافت لیست جایگزین‌های موجود برای استفاده در قالب‌ها
        """
        return {
            'customer_name': 'نام مشتری',
            'purchase_number': 'شماره خرید',
            'invoice_id': 'شناسه سازمانی',
            'order_weight': 'وزن سفارش',
            'customer_price': 'فی فروش',
            'amount_paid': 'مبلغ پرداختی',
            'barnameh': 'شماره بارنامه',
            'barnameh_date': 'تاریخ بارنامه',
            'driver_name': 'نام راننده',
            'driver_phone': 'شماره راننده',
            'extelaf_type': 'نوع اختلاف',
            'extelaf_weight': 'وزن اختلاف',
            'extelaf_amount': 'مبلغ اختلاف',
            'cottage': 'شماره کوتاژ',
            'product_type': 'نوع محصول',
            'product_country': 'کشور محصول',
            'sales_agent_phone': 'شماره تلفن کارشناس فروش',
            'sales_agent_name': 'نام کارشناس فروش',
            'dakheli_number': 'شماره داخلی کارشناس فروش',
            'shenase_takhsis': 'شناسه تخصیص',
            'payment_method': 'شیوۀ پرداخت',
            'port': 'محل بارگیری',
            'loading_time': 'زمان بارگیری',
            'description': 'توضیحات',
            'weight': 'وزن',
            'cargo_type': 'نوع کوتاژ',
            'cargo_country': 'کشور کوتاژ',    
        }

    def save(self, *args, **kwargs):
        # For purchase templates, status is required
        if self.template_type == 'purchase' and not self.status:
            raise ValueError("برای قالب‌های مربوط به خرید، انتخاب وضعیت الزامی است.")
        # For non-purchase templates, status should be null
        elif self.template_type != 'purchase':
            self.status = None
        super().save(*args, **kwargs)

class SmsConfig(models.Model):
    """
    مدل تنظیمات پیامک برای کنترل فعال یا غیرفعال بودن ارسال پیامک‌ها توسط ادمین از طریق پنل ادمین.
    """
    sms_enabled = models.BooleanField(
        default=False,
        verbose_name="ارسال پیامک فعال باشد؟",
        help_text="در صورت غیرفعال بودن، هیچ پیامکی ارسال نخواهد شد."
    )
    
    # تنظیم جدید برای نحوه تشخیص موفقیت ارسال
    assume_success_on_no_error = models.BooleanField(
        default=True,
        verbose_name="فرض موفقیت در عدم وجود خطا؟",
        help_text="اگر فعال باشد، در صورتی که API خطا نده، پیامک موفق تلقی می‌شود (مناسب برای پروداکشن)"
    )

    class Meta:
        verbose_name = "تنظیمات پیامک"
        verbose_name_plural = "تنظیمات پیامک"

    def __str__(self):
        return "تنظیمات پیامک"

    def save(self, *args, **kwargs):
        # فقط یک رکورد تنظیمات باید وجود داشته باشد (Singleton)
        if not self.pk and SmsConfig.objects.exists():
            raise ValueError("فقط یک رکورد تنظیمات پیامک می‌تواند وجود داشته باشد.")
        super().save(*args, **kwargs)

    @staticmethod
    def is_sms_enabled():
        """
        بررسی فعال بودن ارسال پیامک از طریق تنظیمات.
        اگر رکوردی وجود نداشت، پیش‌فرض فعال است.
        """
        config = SmsConfig.objects.first()
        if config is not None:
            return config.sms_enabled
        return False
    
    @staticmethod
    def should_assume_success_on_no_error():
        """
        بررسی اینکه آیا باید در عدم وجود خطا، ارسال پیامک موفق تلقی شود.
        """
        config = SmsConfig.objects.first()
        if config is not None:
            return config.assume_success_on_no_error
        return True  # پیش‌فرض: فرض موفقیت