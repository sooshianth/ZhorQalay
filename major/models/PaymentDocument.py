from django.db import models


class PaymentDocument(models.Model):
    """
    مدل مدرک پرداخت برای خریدهای خارج بازارگاه
    هر خرید می‌تواند چندین مدرک پرداخت داشته باشد
    """
    
    # ارتباط با خرید خارج بازارگاه
    non_bazargah_purchase = models.ForeignKey(
        'major.NonBazargahPurchase',
        on_delete=models.CASCADE,
        verbose_name='خرید خارج بازارگاه',
        related_name='payment_documents'
    )
    
    # فایل مدرک
    document = models.FileField(
        "فایل مدرک",
        upload_to='non_bazargah_payment_docs/',
        help_text="تصویر رسید یا مدرک پرداخت"
    )
    
    # توضیحات
    description = models.TextField("توضیحات", null=True, blank=True)
    
    # کاربری که مدرک را آپلود کرده (معمولاً کارشناس فروش)
    uploaded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='آپلود شده توسط',
        related_name='uploaded_payment_documents'
    )
    
    # زمان آپلود
    uploaded_at = models.DateTimeField("تاریخ آپلود", auto_now_add=True)
    
    class Meta:
        verbose_name = "مدرک پرداخت"
        verbose_name_plural = "مدارک پرداخت"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"مدرک پرداخت برای خرید {self.non_bazargah_purchase.purchase_number} - {self.uploaded_at.strftime('%Y/%m/%d')}"

