from django.db import models
from django.core.exceptions import ValidationError
from django_jalali.db import models as jmodels

class BKILog(models.Model):
    """
    مدل برای ذخیره تاریخچه تعاملات با سرویس BKI
    """
    purchase = models.ForeignKey('core.Purchase', on_delete=models.CASCADE, null=True, blank=True, verbose_name="خرید مرتبط")
    request_type = models.CharField(max_length=50, verbose_name="نوع درخواست")
    request_data = models.TextField(verbose_name="داده‌های ارسالی")
    response_data = models.TextField(verbose_name="داده‌های دریافتی")
    is_successful = models.BooleanField(default=False, verbose_name="آیا موفقیت‌آمیز بود؟")
    error_message = models.TextField(null=True, blank=True, verbose_name="پیام خطا")
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    
    class Meta:
        verbose_name = "لاگ BKI"
        verbose_name_plural = "لاگ‌های BKI"
        ordering = ['-created_at']
    
    def __str__(self):
        if self.purchase:
            return f"{self.request_type} - خرید {self.purchase.id} - {self.created_at}"
        return f"{self.request_type} - {self.created_at}"
