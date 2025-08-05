from django.db import models
from .Invoice import Invoice
from django.forms import ValidationError
from .NonBazargahProduct import NonBazargahProduct

class InvoiceItem(models.Model):

    PRODUCT_TYPE_CHOICES = [
        ('Bazargah', 'بازارگاهی'),
        ('NonBazargah', 'غیر بازارگاهی')
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, verbose_name='فاکتور', related_name='items')
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, verbose_name='نوع محصول', null=True, blank=True)
    non_bazargah_product = models.ForeignKey(NonBazargahProduct, on_delete=models.CASCADE, null=True, blank=True, verbose_name='محصول غیر بازارگاهی')
    cargo_product = models.ForeignKey('core.CargoProduct', on_delete=models.CASCADE, null=True, blank=True, verbose_name='محصول بازارگاهی')
    price = models.BigIntegerField(verbose_name='قیمت واحد', null=True, blank=True)
    amount = models.BigIntegerField(verbose_name='مقدار', null=True, blank=True)

    def clean(self):
        super().clean()

        if self.product_type == 'Bazargah' and not self.cargo_product:
            raise ValidationError('لطفا محصول بازارگاهی را انتخاب کنید.')
        
        if self.product_type == 'NonBazargah' and not self.non_bazargah_product:
            raise ValidationError('لطفا محصول غیر بازارگاهی را انتخاب کنید.')
        
        if self.cargo_product and self.non_bazargah_product:
            raise ValidationError('لطفا فقط یکی از محصولات بازارگاهی یا غیر بازارگاهی را انتخاب کنید.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        product_name = self.get_product_name()
        return f"{product_name} - {self.amount if self.amount else 0}"
    
    def get_product_name(self):
        """دریافت نام محصول"""
        if self.product_type == 'Bazargah' and self.cargo_product:
            return str(self.cargo_product)
        elif self.product_type == 'NonBazargah' and self.non_bazargah_product:
            return str(self.non_bazargah_product)
        return "محصول نامشخص"
    
    def get_total_price(self):
        """محاسبه قیمت کل این آیتم"""
        if self.price and self.amount:
            return self.price * self.amount
        return 0
    
    def get_formatted_total_price(self):
        """قیمت کل فرمت شده"""
        total = self.get_total_price()
        return f"{total:,} ریال" if total > 0 else "0 ریال"

    class Meta:
        verbose_name = 'آیتم فاکتور'
        verbose_name_plural = 'آیتم‌های فاکتور'
