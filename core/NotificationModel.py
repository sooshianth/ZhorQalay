from django.db import models
from django_jalali.db import models as jmodels
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField("پیام نوتیفیکیشن")
    is_read = models.BooleanField("خوانده شده", default=False)
    created_at = jmodels.jDateTimeField("تاریخ ایجاد", default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "نوتیفیکیشن"
        verbose_name_plural = "نوتیفیکیشن‌ها"

    def __str__(self):
        return f"نوتیفیکیشن برای {self.user.username} - {self.message}"
