from .Product import Product
from django.utils.translation import gettext_lazy as _

class NonBazargahProduct(Product):

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