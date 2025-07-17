from django.db import models
from django.contrib.auth.models import User



class ColumnOrderPreference(models.Model):
    """مدل ذخیره ترتیب ستون‌های جدول برای هر کاربر"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    user_role = models.CharField(max_length=50, verbose_name="نقش کاربر")
    column_order = models.JSONField(verbose_name="ترتیب ستون‌ها")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")
    
    class Meta:
        verbose_name = "ترتیب ستون‌های جدول"
        verbose_name_plural = "ترتیب ستون‌های جداول"
        unique_together = ['user', 'user_role']
        indexes = [
            models.Index(fields=['user', 'user_role']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.user_role}" 