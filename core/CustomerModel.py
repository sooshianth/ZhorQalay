from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _ 
from .SalesAgentModel import SalesAgent
from .CargoProductModel import CargoProduct
from django.contrib.postgres.fields import ArrayField


FIELD_OF_ACTIVITY = [
    ('chicken', 'مرغدار'),
    ('livestock', 'گاودار'),
    ('factory', 'کارخانه خوراک'),
    ('trader', 'دلال'),
    ('fish', 'پرورش آبزیان'),
]
class Customer(models.Model):
    phone_number = models.CharField(_("تلفن همراه"), max_length=20, unique=True)
    sales_agent = models.ForeignKey(SalesAgent, on_delete=models.SET_NULL, verbose_name=_("کارشناس فروش"), blank=True, null=True, related_name='customers')
    name = models.CharField(_("نام"), max_length=100, null=True, blank=True)
    city = models.CharField(_("شهر"), max_length=100, null=True, blank=True)
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
    quota = models.CharField(_("سهمیه"),max_length=244, null=True, blank=True)  
    created_at = jmodels.jDateTimeField(_("تاریخ ثبت"), auto_now_add=True, null=True,    blank=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ بروزرسانی"), auto_now=True, null=True, blank=True)   
    is_bazaargah_enjoyer = models.BooleanField(_("داخل بازارگاه؟"), default=True)

    class Meta:
        verbose_name = _("مشتری")
        verbose_name_plural = _("مشتریان")

    @staticmethod
    def get_customer_by_phone(phone_number):
        return Customer.objects.filter(phone_number=phone_number).first()

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
    
    def get_sales_agent(self):
        return self.sales_agent

    def get_last_contact_datetime(self):
        return self.calls.last().date if self.calls.exists() else None

    def __str__(self):
        return f"{self.phone_number} {self.name}"
    
    def clean(self):
        if not self.name:
            raise ValidationError(_('نام را وارد کنید.'))
        if not self.phone_number.startswith('9') or len(self.phone_number) != 10:
            raise ValidationError(_('شماره تلفن باید با 9 شروع شود و 10 رقم باشد.'))
