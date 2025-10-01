from .Product import Product
from django.db import models
from django.utils.translation import gettext_lazy as _

class NonBazargahProduct(Product):
    # فیلد کوتاژ (کد یونیک محصول)
    cottage = models.CharField(
        _('کوتاژ'), 
        unique=True, 
        max_length=50, 
        null=True, 
        blank=True,
        help_text=_('کد یونیک محصول')
    )
    
    # فیلد فی خرید (اطلاعات محرمانه)
    purchase_price = models.PositiveIntegerField(
        _('فی خرید (ریال)'), 
        default=0, 
        help_text=_('قیمت خرید محصول از تامین کننده')
    )

    class Meta:
        verbose_name = _('محصول خارج از بازارگاه')
        verbose_name_plural = _('محصولات خارج از بازارگاه')

    def save(self, *args, **kwargs):
        self.type_of_product = 'NonBazargah'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"
    
    @staticmethod
    def get_active_products():
        """دریافت محصولات فعال خارج از بازارگاه"""
        return NonBazargahProduct.objects.filter(status=True)
    
    def get_purchase_price(self):
        """دریافت فی خرید محصول"""
        return self.purchase_price