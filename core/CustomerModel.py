from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .SalesAgentModel import SalesAgent
from .CargoProductModel import CargoProduct
from django.contrib.postgres.fields import ArrayField


FIELD_OF_ACTIVITY = [
    ('chicken', 'مرغدار'),
    ('livestock', 'دامدار'),
    ('factory', 'کارخانه خوراک'),
    ('fish', 'پرورش آبزیان'),
    ('corporation', 'تعاونی'),
    ('association', 'اتحادیه')
]

class PhoneNumber(models.Model):
    number = models.CharField(_("شماره تلفن"), max_length=20)
    is_primary = models.BooleanField(_("شماره اصلی"), default=False)
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='phone_numbers', verbose_name=_("مشتری"))
    
    class Meta:
        verbose_name = _("شماره تلفن")
        verbose_name_plural = _("شماره های تلفن")
    
    def __str__(self):
        return self.number
    
    def clean(self):
        # اطمینان از فرمت درست شماره تلفن
        self.number = self.number.strip()
        
        # پاکسازی شماره از کاراکترهای غیرعددی
        cleaned_number = ''.join(c for c in self.number if c.isdigit())
        
        # اگر با صفر شروع می‌شود، آن را حذف می‌کنیم
        if cleaned_number.startswith('0'):
            cleaned_number = cleaned_number[1:]
            
        # بررسی معیارهای اصلی
        if not cleaned_number.startswith('9') or len(cleaned_number) != 10:
            raise ValidationError(_('شماره تلفن باید با 9 شروع شود و 10 رقم باشد. لطفاً فرمت صحیح مانند 9123456789 را وارد کنید.'))
        
        # ذخیره شماره پاکسازی شده
        self.number = cleaned_number
        
        # If this is being set as primary, make sure no other numbers for this customer are primary
        if self.is_primary:
            PhoneNumber.objects.filter(customer=self.customer, is_primary=True).exclude(id=self.id).update(is_primary=False)

    def save(self, *args, **kwargs):
        # Always clean before saving
        self.clean()
        super().save(*args, **kwargs)
        
        # If this is the primary number, update the customer's phone_number field
        if self.is_primary:
            self.customer.phone_number = self.number
            self.customer.save(update_fields=['phone_number'])

class Customer(models.Model):
    # phone_number field is no longer unique and will be deprecated
    phone_number = models.CharField(_("تلفن همراه (قدیمی)"), max_length=20, null=True, blank=True,
                                   help_text=_("این فیلد برای سازگاری با نسخه قبلی حفظ شده و به زودی حذف خواهد شد."))
    sales_agent = models.ManyToManyField(SalesAgent, verbose_name=_("کارشناسان فروش"), blank=True, related_name='customers')
    name = models.CharField(_("نام"), max_length=100, null=True, blank=True)
    city = models.CharField(_("شهر"), max_length=100, null=True, blank=True)
    whatsapp_preference = models.BooleanField(_("WhatsApp Preference"), default=False, help_text=_("تمایل به دریافت پیام واتساپ دارد؟"))
    field_of_activity = models.CharField(_("حیطه فعالیت"), max_length=255, blank=True, null=True,
        choices=FIELD_OF_ACTIVITY
    )
    purchase_preferences = models.CharField(_("ترجیحات پرداخت"), max_length=255, blank=True, null=True,
        choices=[('cash', 'نقدی'), ('check', 'چک')]
    )
    product_preferences = models.CharField(_("ترجیحات کالایی"), max_length=255, blank=True, null=True,
        choices=CargoProduct.PRODUCT_TYPES
    )
    contact_start_time = models.TimeField(_("زمان شروع تماس"), blank=True, null=True)
    contact_end_time = models.TimeField(_("زمان پایان تماس"), blank=True, null=True)
    social_media = models.CharField(_("شبکات اجتماعی"), max_length=255, blank=True, null=True,
        help_text=_("مثلا: ایتا و تلگرام، اینستاگرام: آیدیش")
    )
    added_description = models.TextField(_("توضیحات تکمیلی شناسنامه"), blank=True)
    sms_preference = models.BooleanField(_("SMS Preference"), default=True,
        help_text=_("تمایل به دریافت پیامک دارد؟")
    )
    day_of_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="روز هفته برای ارسال پیام (1-7 که 1=شنبه و 7=جمعه است)"
    )
    quota = models.CharField(_("سهمیه"),max_length=244, null=True, blank=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ثبت"), auto_now_add=True, null=True,    blank=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ بروزرسانی"), auto_now=True, null=True, blank=True)
    is_bazaargah_enjoyer = models.BooleanField(_("داخل بازارگاه؟"), default=True)

    class Meta:
        verbose_name = _("مشتری")
        verbose_name_plural = _("مشتریان")

    @staticmethod
    def get_customer_by_phone(phone_number):
        # Clean the phone number first
        if phone_number:
            phone_number = phone_number.strip()
            clean_number = ''.join(c for c in phone_number if c.isdigit())
            if clean_number.startswith('0'):
                clean_number = clean_number[1:]
        else:
            return None
            
        # Try to find a customer with this phone number in the new PhoneNumber model
        phone = PhoneNumber.objects.filter(number=clean_number).first()
        if phone:
            return phone.customer
        
        # Fallback to the old phone_number field
        return Customer.objects.filter(phone_number=clean_number).first()

    def get_primary_phone(self):
        primary = self.phone_numbers.filter(is_primary=True).first()
        if primary:
            return primary.number
        
        # Fallback to first phone or old phone_number
        first_phone = self.phone_numbers.first()
        if first_phone:
            return first_phone.number
        return self.phone_number or ''

    def get_tasks_by_time(self):
        return self.tasks.order_by('due_date')

    def get_calls_by_time(self):
        return self.calls.order_by('date')

    def get_purchases_by_time(self):
        return self.purchases_made.order_by('created_at')

    def get_purchases(self):
        return self.purchases.all()

    def get_calls(self):
        return self.calls.all()

    def get_tasks(self):
        return self.tasks.all()

    def get_name(self):
        return self.name

    def get_sales_agents(self):
        return self.sales_agents.all()

    def get_last_contact_datetime(self):
        return self.calls.last().date if self.calls.exists() else None

    def __str__(self):
        primary_phone = self.get_primary_phone()
        name = self.name or 'بدون نام'
        return f"{primary_phone} {name}" if primary_phone else name
    
    def clean(self):
        if not self.name:
            raise ValidationError(_('نام را وارد کنید.'))
        
        # No need to validate phone_number here as it's now in the PhoneNumber model
