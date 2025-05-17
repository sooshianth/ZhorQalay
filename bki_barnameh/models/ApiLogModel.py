from django.db import models
from django_jalali.db import models as jmodels
from django.utils import timezone
from .BarnamehModel import Barnameh

class BKIApiLog(models.Model):
    barnameh = models.ForeignKey(Barnameh, on_delete=models.CASCADE, related_name='api_logs', verbose_name='بارنامه', null=True, blank=True)
    request_type = models.CharField(max_length=100, verbose_name='نوع درخواست')
    request_data = models.TextField(verbose_name='داده‌های درخواست')
    response_data = models.TextField(verbose_name='داده‌های پاسخ', null=True, blank=True)
    is_successful = models.BooleanField(default=False, verbose_name='موفقیت‌آمیز')
    error_message = models.TextField(verbose_name='پیام خطا', null=True, blank=True)
    debug_info = models.TextField(verbose_name='اطلاعات دیباگ', null=True, blank=True)
    created_at = jmodels.jDateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'لاگ API بازارگاه'
        verbose_name_plural = 'لاگ‌های API بازارگاه'
        
    def __str__(self):
        return f"{self.request_type} - {self.created_at}"
