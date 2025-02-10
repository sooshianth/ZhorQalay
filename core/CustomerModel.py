from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _ 
from .models import CargoProduct

class Customer(models.Model):
    FIELD_OF_ACTIVITY = [
        ('chicken', 'مرغدار'),
        ('livestock', 'گاودار'),
        ('factory', 'کارخانه خوراک'),
        ('trader', 'دلال'),
    ]

    phone_number = models.CharField(_("تلفن همراه"), max_length=20, primary_key=True, unique=True)

    last_name = models.CharField(_("نام خانوادگی"), max_length=100)
    first_name = models.CharField(_("نام"), max_length=100, null=True, blank=True)
    city_province = models.CharField(_("شهر/استان"), max_length=100, null=True, blank=True)

    field_of_activity = models.CharField(_("حیطه فعالیت"), max_length=255, blank=True, null=True,
        choices=FIELD_OF_ACTIVITY
    )

    purchase_preferences = models.CharField(_("ترجیحات پرداخت"), max_length=255, blank=True, null=True,
        choices=[('cash', 'نقدری'), ('check', 'چک')]
    )
    product_preferences = models.CharField(_("ترجیحات کالایی"), max_length=255, blank=True, null=True,
        choices=CargoProduct.PRODUCT_TYPES
    )

    contact_hours = models.CharField(_("ساعات مطلوب تماس"), max_length=50, blank=True, help_text=_("e.g., 9 to 12"))
    social_media = models.CharField(_("شبکات اجتماعی"), max_length=255, blank=True,
        help_text=_("مثلا: ایتا و تلگرام، اینستاگرام: آیدیش")
    )

    profile_description = models.TextField(_("توضیحات تکمیلی شناسنامه"), blank=True)

    sms_preference = models.BooleanField(_("SMS Preference"), default=True,
        help_text=_("تمایل به دریافت پیامک دارد؟")
    )

    quota = models.CharField(_("Quota"),max_length=244, blank=True)  # You might want a more specific field type

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def clean(self):
        if not self.last_name:
            raise ValidationError(_('نام خانوادگی را وارد کنید.'))
        if not self.phone_number.startswith('9') or len(self.phone_number) != 10:
            raise ValidationError(_('شماره تلفن باید با 9 شروع شود و 10 رقم باشد.'))
