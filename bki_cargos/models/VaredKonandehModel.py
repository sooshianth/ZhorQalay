from django.db import models

class VaredKonandeh(models.Model):
    name = models.CharField(max_length=255, verbose_name='نام')
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='شماره تماس')
    email = models.EmailField(blank=True, null=True, verbose_name='ایمیل')
    website = models.URLField(blank=True, null=True, verbose_name='وب‌سایت')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='موجودی حساب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'واردکننده'
        verbose_name_plural = 'واردکنندگان'
        ordering = ['-created_at']

    def __str__(self):
        return self.name 