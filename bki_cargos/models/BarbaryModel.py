from django.db import models

class Barbary(models.Model):
    name = models.CharField(max_length=255, verbose_name='نام')
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='شماره تماس')
    email = models.EmailField(blank=True, null=True, verbose_name='ایمیل')
    description = models.TextField(blank=True, null=True, verbose_name='توضیحات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'باربری'
        verbose_name_plural = 'باربری‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return self.name 