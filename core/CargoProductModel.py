from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class CargoProduct(models.Model):
    PURCHASE_TYPES = [
        ('bazaargah', 'خرید بازارگاه'),
        ('non_bazaargah', 'خرید خارج از بازارگاه'),
]
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
        ['iran', 'ایران']
    ]
    PORTS = [
        ('جنوب', 'جنوب'),
        ('شمال', 'شمال'),
    ]
    
    type = models.CharField(_('نوع خرید'), max_length=25, choices=PURCHASE_TYPES, default='bazaargah')
    cottage = models.CharField(_('کوتاژ'), unique=True, max_length=8, null=True, blank=True)
    price = models.PositiveIntegerField(_('قیمت'), default=0)
    product_type = models.CharField(_('نوع محصول'), max_length=25, choices=PRODUCT_TYPES, )
    country = models.CharField(_('کشور'), max_length=20, choices=COUNTRIES)
    importer_name = models.CharField(_('نام واردکننده/کارخانه'), max_length=100, blank=True, null=True)
    port = models.CharField(_("محل بارگیری"), max_length=25, choices=PORTS, default='جنوب')
    loading_time = models.CharField(_('زمان بارگیری'), max_length=50)
    description = models.CharField(_('توضیحات'), max_length=300, null=True, blank=True)
    weight = models.PositiveIntegerField(_('وزن موجود'), )
    created_at = jmodels.jDateTimeField(_('تاریخ ثبت'), auto_now_add=True)
    last_modified = jmodels.jDateTimeField(_('تاریخ آخرین ویرایش'), auto_now=True)
    status = models.BooleanField(_('فعال/غیرفعال'), default=True)

    class Meta:
        verbose_name = _('محصول')
        verbose_name_plural = _('محصولات')



    def clean(self):
        if self.weight < 0:
            raise ValidationError('وزن باید حداقل 10000 کیلوگرم باشد.')
        self.weight = round(self.weight / 100) * 100
        if self.type == 'bazaargah' and not self.cottage.isdigit() and not len(str(self.cottage)) == 8:
            raise ValidationError('کوتاژ برای خرید بازارگاه باید ۸ رقم عددی باشد.')
        if self.type == 'non_bazaargah' and not self.cottage.isdigit() and not len(str(self.cottage)) == 3:
            raise ValidationError('کوتاژ برای خرید خارج از بازارگاه باید ۳ رقم عددی باشد.')
        
    def get_product_type_display(self):
        return dict(self.PRODUCT_TYPES).get(self.product_type, _('نامشخص'))
    def get_country_display(self):
        return dict(self.COUNTRIES).get(self.country, _('نامشخص'))
    def __str__(self):
        return f"{self.get_product_type_display()} {self.get_country_display()} - {self.cottage}"
    
    def change_status(self):
        temp = self.status
        self.status = not temp

    
    @staticmethod
    def get_active_products():
        return CargoProduct.objects.filter(status=True) 
    