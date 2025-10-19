from django.db import models


class LogViewer(models.Model):
    """
    یک مدل ساده برای نمایش لاگ‌ها در پنل ادمین.
    این مدل هیچ داده‌ای در دیتابیس ذخیره نمی‌کند و فقط برای نمایش استفاده می‌شود.
    """
    
    # یک فیلد dummy برای اینکه Django بتواند مدل را بشناسد
    id = models.AutoField(primary_key=True)
    
    class Meta:
        managed = False  # Django should not create table for this model
        verbose_name = "نمایشگر لاگ"
        verbose_name_plural = "نمایشگر لاگ‌های حافظه"
        db_table = ''  # No database table needed
        app_label = 'core'  # Explicitly set the app label
