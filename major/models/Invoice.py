from django.db import models
from django.forms import ValidationError
from .Hazinah import Hazinah
from django_jalali.db import models as jmodels

class Invoice(models.Model):

    TYPE_CHOICES = [
        ('Hazinah', 'هزینه'),
        ('Income', 'درآمد')
    ]

    hazinah = models.ForeignKey(Hazinah, on_delete=models.CASCADE, verbose_name='هزینه', null=True, blank=True)
    income = models.ForeignKey('bki_barnameh.Barnameh', on_delete=models.CASCADE, verbose_name='درآمد', null=True, blank=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name='نوع فاکتور', null=True, blank=True)
    issue_date = jmodels.jDateField(verbose_name='تاریخ صدور', null=True, blank=True)
    invoice_id = models.CharField(max_length=100, unique=True, verbose_name='شماره فاکتور')
    description = models.CharField(max_length=255, verbose_name='توضیحات', null=True, blank=True)
    attachment = models.FileField(verbose_name='پیوست', upload_to='invoices/attachments/', null=True, blank=True)
    created_at = jmodels.jDateField(verbose_name='تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'فاکتور'
        verbose_name_plural = 'فاکتورها'

    def clean(self):
        super().clean()

        if self.type == 'Hazinah' and not self.hazinah:
            raise ValidationError('لطفا هزینه را انتخاب کنید.')

        if self.type == 'Income' and not self.income:
            raise ValidationError('لطفا درآمد را انتخاب کنید.')
        
        if self.income and  self.hazinah:
            raise ValidationError('لطفا فقط یکی از هزینه یا درآمد را انتخاب کنید.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"فاکتور {self.invoice_id} - {self.get_type_display()}"
    
    def get_total_amount(self):
        """محاسبه کل مبلغ فاکتور از روی آیتم‌ها"""
        total = 0
        for item in self.items.all():
            if item.price and item.amount:
                total += item.price * item.amount
        return total
    
    def get_items_count(self):
        """تعداد آیتم‌های فاکتور"""
        return self.items.count()
    
    def get_related_object(self):
        """دریافت آبجکت مرتبط (هزینه یا درآمد)"""
        if self.type == 'Hazinah' and self.hazinah:
            return self.hazinah
        elif self.type == 'Income' and self.income:
            return self.income
        return None
