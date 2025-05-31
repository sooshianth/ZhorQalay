from django.db import models
import json
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class BulkEditLog(models.Model):
    """مدل ثبت تاریخچه تغییرات ویرایش گروهی"""
    
    ACTION_CHOICES = (
        ('FORM', 'ویرایش فرمی'),
        ('EXCEL', 'ویرایش اکسلی'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="کاربر")
    app_name = models.CharField(max_length=100, verbose_name="نام اپلیکیشن")
    model_name = models.CharField(max_length=100, verbose_name="نام مدل")
    object_id = models.CharField(max_length=100, verbose_name="شناسه آبجکت")
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="نوع عملیات")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="زمان ثبت")
    field_name = models.CharField(max_length=100, verbose_name="نام فیلد")
    old_value = models.TextField(null=True, blank=True, verbose_name="مقدار قبلی")
    new_value = models.TextField(null=True, blank=True, verbose_name="مقدار جدید")
    
    class Meta:
        verbose_name = "لاگ ویرایش گروهی"
        verbose_name_plural = "لاگ‌های ویرایش گروهی"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['app_name', 'model_name']),
            models.Index(fields=['object_id']),
        ]
    
    def __str__(self):
        return f"{self.get_action_type_display()} {self.model_name}:{self.object_id} - {self.field_name}"
    
    @classmethod
    def log_changes(cls, user, app_name, model_name, object_id, action_type, changes_dict):
        """ثبت تغییرات به صورت دسته‌ای
        
        changes_dict: دیکشنری حاوی فیلدها و مقادیر قبل و بعد به صورت:
        {
            'field_name': {'old': old_value, 'new': new_value}
        }
        """
        bulk_logs = []
        
        for field_name, values in changes_dict.items():
            old_value = values.get('old')
            new_value = values.get('new')
            
            # تبدیل مقادیر پیچیده به JSON
            if not isinstance(old_value, (str, int, float, bool, type(None))):
                old_value = json.dumps(old_value)
            if not isinstance(new_value, (str, int, float, bool, type(None))):
                new_value = json.dumps(new_value)
                
            # تبدیل مقادیر ساده به رشته
            old_value = str(old_value) if old_value is not None else None
            new_value = str(new_value) if new_value is not None else None
            
            log = cls(
                user=user,
                app_name=app_name,
                model_name=model_name,
                object_id=object_id,
                action_type=action_type,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value
            )
            bulk_logs.append(log)
        
        # ذخیره دسته‌ای برای کارایی بیشتر
        if bulk_logs:
            cls.objects.bulk_create(bulk_logs)
        
        return len(bulk_logs)
    
    @classmethod
    def get_object_history(cls, app_name, model_name, object_id):
        """دریافت تاریخچه تغییرات یک آبجکت"""
        return cls.objects.filter(
            app_name=app_name,
            model_name=model_name,
            object_id=object_id
        ).order_by('-timestamp')
    
    def restore_value(self):
        """بازگرداندن مقدار به حالت قبلی"""
        from django.apps import apps
        
        try:
            # دریافت مدل و آبجکت
            model = apps.get_model(self.app_name, self.model_name)
            obj = model.objects.get(id=self.object_id)
            
            # تبدیل مقدار قدیمی از رشته به نوع مناسب
            old_value = self.old_value
            
            # اگر مقدار قدیمی JSON باشد، آن را پارس کنیم
            if old_value and (old_value.startswith('{') or old_value.startswith('[')):
                try:
                    old_value = json.loads(old_value)
                except json.JSONDecodeError:
                    pass
            
            # اعمال مقدار قدیمی
            setattr(obj, self.field_name, old_value)
            obj.save(update_fields=[self.field_name])
            
            return True, f"فیلد {self.field_name} به مقدار قبلی بازگردانده شد"
        except Exception as e:
            return False, f"خطا در بازگرداندن مقدار: {str(e)}"
