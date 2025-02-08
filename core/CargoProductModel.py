from django.db import models
from django.core.exceptions import ValidationError

class CargoProduct(models.Model):
    PRODUCT_TYPES = [
        ('corn', 'ذرت'),
        ('barley', 'جو'),
        ('soy_meal', 'کنجاله سویا'),
        ('rapeseed_meal', 'کنجاله کلزا'),
        ('extracted_soy', 'سویا استحصالی'),
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
    ]

    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)
    country = models.CharField(max_length=20, choices=COUNTRIES)
    importer_name = models.CharField(max_length=100)
    quota = models.PositiveIntegerField()
    loading_time = models.CharField(max_length=50)
    weight = models.PositiveIntegerField()
    description = models.CharField(max_length=300, null=True, blank=True)

    def clean(self):
        if self.weight < 10000:
            raise ValidationError('وزن باید حداقل 10000 کیلوگرم باشد.')
        self.weight = round(self.weight / 100) * 100

    def __str__(self):
        return f"{self.product_type} from {self.country} - {self.importer_name}"