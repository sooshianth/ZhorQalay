from django.db import models
from django.utils import timezone
from core.PurchaseModel import Purchase

class WhatsappLog(models.Model):
    recipient_number = models.CharField(max_length=20)
    message = models.TextField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_from = models.ForeignKey('WhatsappNumber', on_delete=models.SET_NULL, null=True, blank=True)
    template_type = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=10, default='sent', verbose_name="وضعیت")
    purchase = models.ForeignKey('core.Purchase', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="خرید")

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
        ('purchase', 'قالب مربوط به خرید'),
        ('product_notification', 'قالب ارسال محصولات'),
        ('marketing', 'قالب تبلیغاتی'),
    ]
    
    STATUS_CHOICES = Purchase.STATUS_CHOICES
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        blank=True, 
        null=True, 
        verbose_name="وضعیت خرید (برای قالب‌های خرید)",
        help_text="این فیلد فقط برای قالب‌های مربوط به خرید ضروری است"
    )
    name = models.CharField(max_length=100, verbose_name="نام قالب")
    template_type = models.CharField(
        max_length=30, 
        choices=TEMPLATE_TYPES, 
        default='purchase', 
        verbose_name="نوع قالب"
    )
    content = models.TextField(verbose_name="محتوای قالب")
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="توضیحات",
        help_text="توضیح کوتاهی درباره کاربرد این قالب"
    )
    variables = models.JSONField(
        default=dict, 
        verbose_name="متغیرهای قابل استفاده",
        help_text="متغیرهای استخراج شده از محتوای قالب"
    )
    is_active = models.BooleanField(
        default=False, 
        verbose_name="قالب پیش‌فرض",
        help_text="آیا این قالب به عنوان پیش‌فرض استفاده شود؟"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")
    is_for_salesmen = models.BooleanField(
        default=False, 
        verbose_name="برای کارشناس فروش",
        help_text="آیا این قالب برای کارشناسان فروش قابل استفاده است؟"
    )

    def __str__(self):
        status_part = f" - {self.get_status_display()}" if self.status else ""
        active_part = " (پیش‌فرض)" if self.is_active else ""
        return f"{self.name} ({self.get_template_type_display()}){status_part}{active_part}"

    def clean(self):
        """اعتبارسنجی قالب"""
        from django.core.exceptions import ValidationError
        
        # برای قالب‌های خرید، وضعیت ضروری است
        if self.template_type == 'purchase' and not self.status:
            raise ValidationError({
                'status': 'برای قالب‌های مربوط به خرید، انتخاب وضعیت ضروری است.'
            })
        
        # برای قالب‌های غیر خرید، وضعیت نباید تنظیم شود
        if self.template_type != 'purchase' and self.status:
            self.status = None

    def save(self, *args, **kwargs):
        """ذخیره قالب با اعمال قوانین تجاری"""
        # اجرای اعتبارسنجی
        self.clean()
        
        # اگر این قالب پیش‌فرض می‌شود، بقیه قالب‌های مشابه را غیرفعال کن
        if self.is_active:
            if self.template_type == 'purchase' and self.status:
                # برای قالب‌های خرید، بر اساس وضعیت
                WhatsappTemplate.objects.filter(
                    status=self.status, 
                    template_type='purchase', 
                    is_active=True
                ).exclude(pk=self.pk).update(is_active=False)
            else:
                # برای قالب‌های دیگر، بر اساس نوع
                WhatsappTemplate.objects.filter(
                    template_type=self.template_type, 
                    is_active=True
                ).exclude(pk=self.pk).update(is_active=False)
        
        # استخراج متغیرها از محتوا
        import re
        variables = []
        for match in re.finditer(r'{{(.+?)}}', self.content):
            var_name = match.group(1).strip()
            if var_name not in variables:
                variables.append(var_name)
        self.variables = {'used_variables': variables}
        
        super().save(*args, **kwargs)

    @property
    def character_count(self):
        """تعداد کاراکترهای قالب"""
        return len(self.content)
    
    @property
    def message_count(self):
        """تعداد پیام‌های مورد نیاز (بر اساس 160 کاراکتر)"""
        return max(1, (self.character_count + 159) // 160)
    
    @property
    def used_variables(self):
        """لیست متغیرهای استفاده شده در قالب"""
        return self.variables.get('used_variables', [])

    class Meta:
        verbose_name = "قالب واتساپ"
        verbose_name_plural = "قالب‌های واتساپ"
        ordering = ['template_type', '-is_active', 'name']
        
        # محدودیت یکتایی: فقط یک قالب پیش‌فرض برای هر نوع و وضعیت
        constraints = [
            models.UniqueConstraint(
                fields=['template_type', 'status'],
                condition=models.Q(is_active=True, template_type='purchase'),
                name='unique_active_purchase_template_per_status'
            ),
            models.UniqueConstraint(
                fields=['template_type'],
                condition=models.Q(is_active=True) & ~models.Q(template_type='purchase'),
                name='unique_active_template_per_type'
            ),
        ]
        
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
        }




class WhatsappQueue(models.Model):
    NOTIFICATION_TYPES = [
        ('new_purchase', 'اطلاع رسانی خرید جدید'),
        ('payment_confirmation', 'تایید پرداخت'),
        ('address_notification', 'اطلاع رسانی آدرس'),
        ('barnameh_notification', 'اطلاع رسانی بارنامه'),
        ('extelaf_notification', 'اطلاع رسانی اختلاف'),
        ('cottage_notification', 'اطلاع رسانی کوتاژ'),
        ('marketing', 'پیام تبلیغاتی'),
        ('custom', 'پیام سفارشی'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار ارسال'),
        ('sent', 'ارسال شده'),
        ('failed', 'ارسال ناموفق'),
        ('suspended', 'معلق'),
    ]

    recipient_number = models.CharField(max_length=20, verbose_name="شماره گیرنده")
    message = models.TextField(verbose_name="متن پیام")
    template_type = models.CharField(max_length=50, null=True, blank=True, verbose_name="نوع قالب")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='custom', verbose_name="نوع اطلاع رسانی")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    is_suspended = models.BooleanField(default=False, verbose_name="معلق شده")
    retry_count = models.IntegerField(default=0, verbose_name="تعداد تلاش مجدد")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    scheduled_for = models.DateTimeField(default=timezone.now, verbose_name="زمان ارسال")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ ارسال")
    purchase = models.ForeignKey('core.Purchase', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="خرید")
    
    def __str__(self):
        return f"WhatsApp to {self.recipient_number} - {self.get_status_display()}"
        
    def save(self, *args, **kwargs):
        # اگر فقط purchase_id وارد شده باشد و purchase خالی باشد، سعی کنیم purchase را پیدا کنیم
        if self.purchase_id is not None and self.purchase is None:
            try:
                from core.PurchaseModel import Purchase
                self.purchase = Purchase.objects.get(pk=self.purchase_id)
            except:
                pass
        
        # اگر purchase وارد شده باشد و purchase_id خالی باشد، purchase_id را از purchase استخراج کنیم
        if self.purchase is not None and self.purchase_id is None:
            self.purchase_id = self.purchase.id
            
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "صف واتساپ"
        verbose_name_plural = "صف پیام‌های واتساپ"
        ordering = ['scheduled_for', 'created_at']

