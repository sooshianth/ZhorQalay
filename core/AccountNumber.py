from django.db import models


class AccountNumber(models.Model):
    """
    مدل شماره حساب برای ذخیره اطلاعات حساب‌های بانکی مشتریان
    این اطلاعات برای تسریع در ثبت فیش‌های پرداخت استفاده می‌شود
    """
    
    # ارتباط با مشتری
    customer = models.ForeignKey(
        'core.Customer',
        on_delete=models.CASCADE,
        verbose_name='مشتری',
        related_name='account_numbers'
    )
    
    # اطلاعات بانکی
    bank_name = models.CharField("نام بانک", max_length=100)
    account_number = models.CharField("شماره حساب", max_length=50)
    account_holder_name = models.CharField("نام صاحب حساب", max_length=255)
    
    # توضیحات اضافی
    description = models.TextField("توضیحات", null=True, blank=True)
    
    # فعال/غیرفعال
    is_active = models.BooleanField("فعال", default=True)
    
    # زمان ایجاد و بروزرسانی
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("تاریخ بروزرسانی", auto_now=True)
    
    class Meta:
        verbose_name = "شماره حساب"
        verbose_name_plural = "شماره‌های حساب"
        ordering = ['-created_at']
        unique_together = ['customer', 'account_number']  # هر مشتری نمی‌تواند یک شماره حساب تکراری داشته باشد
    
    def __str__(self):
        return f"{self.customer.name} - {self.bank_name} - {self.account_number}"
