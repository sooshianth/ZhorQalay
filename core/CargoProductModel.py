from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .extensions import utils

class CargoProduct(models.Model):
    PRODUCT_TYPES = [
        ('corn', 'ذرت'),
        ('barley', 'جو'),
        ('soy_meal', 'کنجاله سویا'),
        ('sunflower_meal', 'کنجاله آفتابگردان'),
        ('rapeseed_meal', 'کنجاله کلزا'),
        ('local_extracted_soy', ' سویا استحصالی داخلی'),
        ('foreign_extracted_soy', ' سویا استحصالی خارجی'),
        ('soy_grain', 'دان سویا'),
        ('cotton_seed', 'دان پنبه'),
        ('alfalfa', 'یونجه'),
    ]

    COUNTRIES = [
        ('argentina', 'آرژانتین'),
        ('brazil', 'برزیل'),
        ('ukraine', 'اوکراین'),
        ('india', 'هند'),
        ('russia', 'روسیه'),
        ('kazakhstan', 'قزاقستان'),
        ('turkey', 'ترکیه'),
        ('canada', 'کانادا'),
        ('australia', 'استرالیا'),
        ('serbia', 'صربستان'),
    ]

    cottage = models.PositiveIntegerField(_('کوتاژ'), primary_key=True)
    product_type = models.CharField(_('نوع محصول'), max_length=25, choices=PRODUCT_TYPES, )
    country = models.CharField(_('کشور'), max_length=20, choices=COUNTRIES)
    importer_name = models.CharField(_('نام صادرکننده'), max_length=100)
    loading_time = models.CharField(_('زمان بارگیری'), max_length=50)
    description = models.CharField(_('توضیحات'), max_length=300, null=True, blank=True)
    weight = models.PositiveIntegerField(_('وزن موجود'), )
    created_at = models.DateTimeField(_('تاریخ ثبت'), auto_now_add=True)
    last_modified = models.DateTimeField(_('تاریخ آخرین ویرایش'), auto_now=True)
    status = models.BooleanField(_('فعال/غیرفعال'), default=True)

    class Meta:
        verbose_name = _('محصول')
        verbose_name_plural = _('محصولات')



    def clean(self):
        if self.weight < 10000:
            raise ValidationError('وزن باید حداقل 10000 کیلوگرم باشد.')
        self.weight = round(self.weight / 100) * 100
        if len(str(self.cottage)) != 8:
            raise ValidationError('کوتاژ باید ۸ رقمی باشد.')
        
    def __str__(self):
        return f"{self.product_type} از {self.country} - {self.cottage}"
    
    def change_status(self):
        temp = self.status
        self.status = not temp

    def return_created(self):
        return utils.time_convertor(self.created_at)
    
    @staticmethod
    def get_active_products():
        return CargoProduct.objects.filter(status=True) 