from django.db import models
from django_jalali.db import models as jmodels
from django.utils import timezone

class ExcelFile(models.Model):
    file = models.FileField(upload_to='barnameh_excel_files/', verbose_name='فایل اکسل')
    name = models.CharField(max_length=255, verbose_name='نام فایل')
    uploaded_at = jmodels.jDateTimeField(default=timezone.now, verbose_name='تاریخ آپلود')
    processed = models.BooleanField(default=False, verbose_name='پردازش شده')
    rows_count = models.IntegerField(default=0, verbose_name='تعداد ردیف‌ها')
    processed_rows = models.IntegerField(default=0, verbose_name='ردیف‌های پردازش شده')
    
    class Meta:
        verbose_name = 'فایل اکسل بارنامه'
        verbose_name_plural = 'فایل‌های اکسل بارنامه'
        
    def __str__(self):
        return self.name
