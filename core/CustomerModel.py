from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _ 
from .SalesAgentModel import SalesAgent
from .CargoProductModel import CargoProduct
from django.contrib.postgres.fields import ArrayField
from .extensions import utils


FIELD_OF_ACTIVITY = [
    ('chicken', 'مرغدار'),
    ('livestock', 'گاودار'),
    ('factory', 'کارخانه خوراک'),
    ('trader', 'دلال'),
    ('fish', 'پرورش آبزیان'),
]
class Customer(models.Model):

    # شماره تلفن
    phone_number = models.CharField(_("تلفن همراه"), max_length=20, unique=True)

    # کارشناس فروش
    sales_agent = models.ForeignKey(SalesAgent, on_delete=models.SET_NULL, verbose_name=_("کارشناس فروش"), blank=True, null=True, related_name='customers')

    # اسم
    name = models.CharField(_("نام"), max_length=100, null=True, blank=True)

    # شهر
    city = models.CharField(_("شهر"), max_length=100, null=True, blank=True)

    # زمینه فعالیت
    field_of_activity = models.CharField(_("حیطه فعالیت"), max_length=255, blank=True, null=True,
        choices=FIELD_OF_ACTIVITY
    )

    # ترجیحات خرید
    purchase_preferences = models.CharField(_("ترجیحات پرداخت"), max_length=255, blank=True, null=True,
        choices=[('cash', 'نقدری'), ('check', 'چک')]
    )
    # ترحیجات کالایی
    product_preferences = models.CharField(_("ترجیحات کالایی"), max_length=255, blank=True, null=True,
        choices=CargoProduct.PRODUCT_TYPES
    )

    # ترجیحات ساعت تماس
    contact_start_time = models.TimeField(_("زمان شروع تماس"), blank=True, null=True)
    contact_end_time = models.TimeField(_("زمان پایان تماس"), blank=True, null=True)

    # فضای مجازی
    social_media = models.CharField(_("شبکات اجتماعی"), max_length=255, blank=True, null=True,
        help_text=_("مثلا: ایتا و تلگرام، اینستاگرام: آیدیش")
    )

    # توضیحات بیشتر
    added_description = models.TextField(_("توضیحات تکمیلی شناسنامه"), blank=True)

    # ترجیحات پیامکی
    sms_preference = models.BooleanField(_("SMS Preference"), default=True,
        help_text=_("تمایل به دریافت پیامک دارد؟")
    )

    # سهمیه
    quota = models.CharField(_("Quota"),max_length=244, blank=True)  # You might want a more specific field type

    #آدرس
    #address = models.TextField(_("آدرس"), blank=True, null=True)

    #آخرین تماس با مشتری
    # last_contact_date = models.DateTimeField(_("تاریخ آخرین تماس"), blank=True, null=True)
    created_at = models.DateTimeField(_("تاریخ ثبت"), auto_now_add=True, null=True,    blank=True)
    updated_at = models.DateTimeField(_("تاریخ بروزرسانی"), auto_now=True, null=True, blank=True)   


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

    def return_created_at(self):
        return utils.time_convertor(self.created_at)
    def return_updated_at(self):
        return utils.time_convertor(self.updated_at)

    def __str__(self):
        return f"{self.phone_number} {self.name}"
    
    def clean(self):
        if not self.name:
            raise ValidationError(_('نام را وارد کنید.'))
        if not self.phone_number.startswith('9') or len(self.phone_number) != 10:
            raise ValidationError(_('شماره تلفن باید با 9 شروع شود و 10 رقم باشد.'))
