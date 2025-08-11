from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from major.models.Product import Product

class VaredKonandeh(models.Model):
    name = models.CharField(max_length=50, verbose_name='نام', blank=True, null=True)
    phone_number = models.CharField(max_length=11, verbose_name='شماره تماس', blank=True, null=True)
    email = models.EmailField(max_length=50, verbose_name='ایمیل', blank=True, null=True)
    website = models.URLField(max_length=200, verbose_name='وبسایت', blank=True, null=True)
    balance = models.IntegerField(verbose_name='کیف پول', blank=True, null=True)
    address = models.CharField(max_length=300, verbose_name='آدرس', null=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name='فعال/غیرفعال', null=True, blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'وارد کننده'
        verbose_name_plural = 'واردکنندگان'
    
class Barbary(models.Model):
    name = models.CharField(max_length=50, verbose_name='نام', blank=True, null=True)
    phone_number = models.CharField(max_length=11, verbose_name='شماره تماس', blank=True, null=True)
    email = models.EmailField(max_length=50, verbose_name='ایمیل', blank=True, null=True)
    description = models.CharField(max_length=200, verbose_name='توضیحات', blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'باربری'
        verbose_name_plural = 'باربری ها'

class VaredKonandehTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'واریز'),
        ('withdrawal', 'برداشت'),
    ]
    vared_konandeh = models.ForeignKey(VaredKonandeh, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.IntegerField(verbose_name='مبلغ(ریال)', blank=True, null=True)
    description = models.CharField(max_length=200, verbose_name='توضیحات', blank=True, null=True)
    type = models.CharField(max_length=20, verbose_name='نوع تراکنش', choices=TRANSACTION_TYPES, default='deposit')
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    account_number = models.CharField(max_length=20, verbose_name='شماره حساب', blank=True, null=True)
    
    def __str__(self):
        return f"{self.vared_konandeh.name} - {self.amount}"
    
    class Meta:
        verbose_name = 'تراکنش وارد کننده'
        verbose_name_plural = 'تراکنش های وارد کننده'
 

class CargoProduct(Product):
    PRODUCT_TYPES = [
        ('corn', 'ذرت'),
        ('barley', 'جو'),
        ('soy_meal', 'کنجاله سویا'),
        ('sunflower_meal', 'کنجاله آفتابگردان'),
        ('rapeseed_meal', 'کنجاله کلزا'),
        ('local_extracted_soy', 'کنجاله سویا استحصالی از دانه داخلی'),
        ('foreign_extracted_soy', 'کنجاله سویا استحصالی از دانه خارجی'),
        ('soy_grain', 'دان سویا'),
        ('cotton_seed', 'دان پنبه'),
        ('alfalfa', 'یونجه'),
        ('other', 'سایر')
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
        ('romania', 'رومانی'),
        ('iran', 'ایران'),
        ('other', 'سایر')
    ]
    PORTS = [
        ('امام خمینی', 'امام خمینی'),
        ('شهید رجایی', 'شهید رجایی'),
        ('امیرآباد', 'امیرآباد'),
        ('انزلی', 'انزلی'),
        ('بهشهر', 'بهشهر'),
        ('فریدونکنار', 'فریدونکنار'),
        ('سایر', 'سایر')
    ]
    
    cottage = models.CharField(_('کوتاژ'), unique=True, max_length=8, null=True, blank=True)
    company_price = models.PositiveIntegerField("فی خرید(ریال)", default=0)
    customer_price = models.PositiveIntegerField("فی فروش(ریال)", default=0)
    product_type = models.CharField(_('نوع محصول'), max_length=25, choices=PRODUCT_TYPES, )
    country = models.CharField(_('کشور'), max_length=20, choices=COUNTRIES)
    vared_konandeh = models.ForeignKey(VaredKonandeh, on_delete=models.CASCADE, null=True, blank=True)
    port = models.CharField(_("محل بارگیری"), max_length=25, choices=PORTS, default='بندر امام خمینی')
    loading_time = models.CharField(_('زمان بارگیری'), max_length=50, null=True, blank=True)
    weight = models.PositiveIntegerField(_('وزن موجود'), default=100000000, null=True, blank=True)
    last_modified = jmodels.jDateTimeField(_('تاریخ آخرین ویرایش'), auto_now=True)
    barbary = models.ForeignKey(Barbary, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = _('محصول')
        verbose_name_plural = _('محصولات')

    # وقتی نیاز به ثبت قیمت دقیق داریم، از این تابع استفاده می‌کنیم
    @classmethod
    def update_exact_price(cls, product_id, field_name, value):
        """
        به‌روزرسانی مستقیم قیمت بدون اعمال هرگونه منطق بیزینسی یا اعتبارسنجی
        """
        from django.db import connection
        with connection.cursor() as cursor:
            table_name = cls._meta.db_table
            cursor.execute(
                f"UPDATE {table_name} SET {field_name} = %s WHERE id = %s",
                [value, product_id]
            )
        return True

    def clean(self):
        if self.weight < 0:
            raise ValidationError('وزن باید حداقل 10000 کیلوگرم باشد.')
        self.weight = round(self.weight / 100) * 100
        
        # برای اطمینان از صحت قیمت‌ها، بدون تغییر و گرد کردن آنها
        # اگر کد پنهانی برای گرد کردن وجود داشته، باید اینجا بررسی شود
        
        if self.type_of_product == 'bazaargah' and not self.cottage.isdigit() and not len(str(self.cottage)) == 8:
            raise ValidationError('کوتاژ برای خرید بازارگاه باید ۸ رقم عددی باشد.')
        if self.type_of_product == 'non_bazaargah' and not self.cottage.isdigit() and not len(str(self.cottage)) == 3:
            raise ValidationError('کوتاژ برای خرید خارج از بازارگاه باید ۳ رقم عددی باشد.')
        if self.customer_price != 0 and self.customer_price < 50000:
            raise ValidationError('فی فروش باید حداقل 50000 ریال باشد.')
        if self.company_price != 0 and self.company_price < 50000:
            raise ValidationError('فی خرید باید حداقل 50000 ریال باشد.')

    def save(self, *args, **kwargs):
        self.type_of_product = 'Bazargah'
        self.name = self.product_type
        super().save(*args, **kwargs)

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
    

