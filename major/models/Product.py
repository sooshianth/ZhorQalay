from django.db import models
from django_jalali.db import models as jmodels
from django.utils.translation import gettext_lazy as _

class Product(models.Model):
    TYPE_CHOICES = [
        ('Bazargah', 'بازارگاه'),
        ('NonBazargah', 'خارج از بازارگاه')
    ]
    name = models.CharField(_('نام محصول'), max_length=100, null=True, blank=True)
    description = models.CharField(_('توضیحات'), max_length=300, null=True, blank=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ثبت'), auto_now_add=True)
    status = models.BooleanField(_('فعال/غیرفعال'), default=True, null=True, blank=True)
    type_of_product = models.CharField(_('نوع محصول'), max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    vared_konandeh = models.ForeignKey('core.VaredKonandeh', on_delete=models.CASCADE, null=True, blank=True)


    class Meta:
        abstract = True