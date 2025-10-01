from django.db import models


class Phish(models.Model):
    """
    مدل فیش پرداخت برای خریدهای خارج بازارگاه
    هر خرید می‌تواند چندین فیش پرداخت داشته باشد
    """
    
    # ارتباط با خرید خارج بازارگاه
    non_bazargah_purchase = models.ForeignKey(
        'major.NonBazargahPurchase', 
        on_delete=models.CASCADE, 
        verbose_name='خرید خارج بازارگاه',
        related_name='phishes'
    )
    
    # ارتباط با شماره حساب (برای auto-fill)
    account = models.ForeignKey(
        'core.AccountNumber',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='شماره حساب',
        related_name='phishes',
        help_text='انتخاب شماره حساب برای تکمیل خودکار اطلاعات'
    )
    
    # اطلاعات بانکی و پرداخت
    bank_name = models.CharField("نام بانک", max_length=100)
    account_number = models.CharField("شماره حساب", max_length=50)
    depositor_name = models.CharField("نام واریزکننده", max_length=255)
    amount = models.PositiveIntegerField("مبلغ (ریال)")
    transaction_date = models.DateField("تاریخ تراکنش")
    
    # توضیحات اضافی
    description = models.TextField("توضیحات", null=True, blank=True)
    
    # فیلدهای زمانی برای ردیابی
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("تاریخ بروزرسانی", auto_now=True)
    
    class Meta:
        verbose_name = "فیش پرداخت"
        verbose_name_plural = "فیش‌های پرداخت"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"فیش {self.depositor_name} - {self.amount:,} ریال - {self.non_bazargah_purchase.purchase_number}"

