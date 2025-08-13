from django.db import models
from .BasePurchase import BasePurchase
from .NonBazargahProduct import NonBazargahProduct

class NonBazargahPurchase(BasePurchase):
    # Override customer field with specific related_name
    customer = models.ForeignKey('core.Customer', on_delete=models.CASCADE, verbose_name='مشتری', null=True, blank=True, related_name='non_bazargah_purchases_made')
    
    UNIT_CHOICES = [
        ('Kilo', 'کیلوگرم'),
        ('Ton', 'تن'),
        ('Kiseh', 'کیسه'),
    ]

    STATUS_CHOICES = [
        ('initiated', 'شروع شده')
        # بعدا باید تکمیل بشه
    ]
    
    purchase_number = models.CharField("شماره خرید", max_length=7, blank=True, null=True, unique=True)
    product = models.ForeignKey(NonBazargahProduct, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="محصول", related_name="non_bazargah_purchases")
    unit = models.CharField(max_length=100, null=True, blank=True, verbose_name="واحد", choices=UNIT_CHOICES)
    state = models.CharField(max_length=100, null=True, blank=True, verbose_name="وضعیت", default='initiated')

    class Meta:
        verbose_name = "خرید خارج بازارگاه"
        verbose_name_plural = "خریدهای خارج بازارگاه"

    def __str__(self):
        return f"خرید: {self.purchase_number} - {self.product.name if self.product else 'Unknown Product'}"