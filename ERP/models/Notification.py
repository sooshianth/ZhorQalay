from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('purchase', 'خرید جدید'),
        ('payment', 'تایید پرداخت'),
        ('allocation', 'تخصیص'),
        ('shipping', 'حمل و نقل'),
        ('delivery', 'تحویل'),
        ('difference', 'اختلاف'),
        ('system', 'سیستمی'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'عادی'),
        ('medium', 'مهم'),
        ('high', 'فوری'),
        ('critical', 'بحرانی')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='erp_notifications')
    title = models.CharField("عنوان", max_length=200)
    message = models.TextField("پیام")
    notification_type = models.CharField("نوع اعلان", max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField("اولویت", max_length=10, choices=PRIORITY_LEVELS, default='low')
    is_read = models.BooleanField("خوانده شده", default=False)
    created_at = jmodels.jDateTimeField("تاریخ ایجاد", auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"