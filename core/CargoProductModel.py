from django.db import models
from django.core.exceptions import ValidationError
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

    product_type = models.CharField(max_length=25, choices=PRODUCT_TYPES)
    country = models.CharField(max_length=20, choices=COUNTRIES)
    importer_name = models.CharField(max_length=100)
    quota = models.PositiveIntegerField()
    loading_time = models.CharField(max_length=50)
    status = models.BooleanField(default=True)
    weight = models.PositiveIntegerField()
    description = models.CharField(max_length=300, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)


    def clean(self):
        if self.weight < 10000:
            raise ValidationError('وزن باید حداقل 10000 کیلوگرم باشد.')
        self.weight = round(self.weight / 100) * 100

    def __str__(self):
        return f"{self.product_type} from {self.country} - {self.importer_name}"
    
    def change_status(self):
        temp = self.status
        self.status = not temp

    def return_created(self):
        return utils.time_convertor(self.created_at)