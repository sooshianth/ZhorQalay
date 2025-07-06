from django.db import models
import json
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

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


class TableFilterConfiguration(models.Model):
    """مدل تنظیمات فیلتر جدول"""
    
    COLUMN_TYPE_CHOICES = [
        ('text', 'متن'),
        ('number', 'عدد'),
        ('date', 'تاریخ'),
        ('boolean', 'بولین'),
        ('status', 'وضعیت'),
        ('choice', 'انتخابی'),
    ]
    
    table_name = models.CharField(max_length=100, verbose_name="نام جدول")
    column_id = models.CharField(max_length=100, verbose_name="شناسه ستون")
    column_name = models.CharField(max_length=100, verbose_name="نام ستون")
    column_type = models.CharField(max_length=20, choices=COLUMN_TYPE_CHOICES, default='text', verbose_name="نوع ستون")
    is_filterable = models.BooleanField(default=True, verbose_name="قابل فیلتر")
    is_sortable = models.BooleanField(default=True, verbose_name="قابل مرتب‌سازی")
    is_visible = models.BooleanField(default=True, verbose_name="قابل نمایش")
    column_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب ستون")
    
    # تنظیمات اضافی برای انواع مختلف ستون‌ها
    choices_json = models.TextField(blank=True, null=True, verbose_name="گزینه‌های انتخابی (JSON)")
    date_format = models.CharField(max_length=50, blank=True, null=True, verbose_name="فرمت تاریخ")
    number_format = models.CharField(max_length=50, blank=True, null=True, verbose_name="فرمت عدد")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")
    
    class Meta:
        verbose_name = "تنظیمات فیلتر جدول"
        verbose_name_plural = "تنظیمات فیلتر جداول"
        unique_together = ['table_name', 'column_id']
        ordering = ['table_name', 'column_order', 'column_id']
        indexes = [
            models.Index(fields=['table_name']),
            models.Index(fields=['table_name', 'column_id']),
        ]
    
    def __str__(self):
        return f"{self.table_name} - {self.column_name}"
    
    @property
    def choices_list(self):
        """بازگرداندن لیست گزینه‌های انتخابی"""
        if self.choices_json:
            try:
                return json.loads(self.choices_json)
            except json.JSONDecodeError:
                return []
        return []
    
    @choices_list.setter
    def choices_list(self, value):
        """تنظیم لیست گزینه‌های انتخابی"""
        if value:
            self.choices_json = json.dumps(value, ensure_ascii=False)
        else:
            self.choices_json = None


class UserTableFilterState(models.Model):
    """مدل ذخیره وضعیت فیلتر کاربر"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    table_name = models.CharField(max_length=100, verbose_name="نام جدول")
    filter_state_json = models.TextField(verbose_name="وضعیت فیلتر (JSON)")
    sort_state_json = models.TextField(blank=True, null=True, verbose_name="وضعیت مرتب‌سازی (JSON)")
    column_visibility_json = models.TextField(blank=True, null=True, verbose_name="نمایش ستون‌ها (JSON)")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")
    
    class Meta:
        verbose_name = "وضعیت فیلتر کاربر"
        verbose_name_plural = "وضعیت‌های فیلتر کاربران"
        unique_together = ['user', 'table_name']
        indexes = [
            models.Index(fields=['user', 'table_name']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.table_name}"
    
    @property
    def filter_state(self):
        """بازگرداندن وضعیت فیلتر"""
        try:
            return json.loads(self.filter_state_json) if self.filter_state_json else {}
        except json.JSONDecodeError:
            return {}
    
    @filter_state.setter
    def filter_state(self, value):
        """تنظیم وضعیت فیلتر"""
        self.filter_state_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def sort_state(self):
        """بازگرداندن وضعیت مرتب‌سازی"""
        try:
            return json.loads(self.sort_state_json) if self.sort_state_json else {}
        except json.JSONDecodeError:
            return {}
    
    @sort_state.setter
    def sort_state(self, value):
        """تنظیم وضعیت مرتب‌سازی"""
        self.sort_state_json = json.dumps(value, ensure_ascii=False)
    
    @property
    def column_visibility(self):
        """بازگرداندن وضعیت نمایش ستون‌ها"""
        try:
            return json.loads(self.column_visibility_json) if self.column_visibility_json else {}
        except json.JSONDecodeError:
            return {}
    
    @column_visibility.setter
    def column_visibility(self, value):
        """تنظیم وضعیت نمایش ستون‌ها"""
        self.column_visibility_json = json.dumps(value, ensure_ascii=False)


class TableFilterPreset(models.Model):
    """مدل پیش‌تنظیمات فیلتر جدول"""
    
    name = models.CharField(max_length=100, verbose_name="نام پیش‌تنظیم")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    table_name = models.CharField(max_length=100, verbose_name="نام جدول")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    is_public = models.BooleanField(default=False, verbose_name="عمومی")
    is_default = models.BooleanField(default=False, verbose_name="پیش‌فرض")
    
    filter_config_json = models.TextField(verbose_name="تنظیمات فیلتر (JSON)")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")
    
    class Meta:
        verbose_name = "پیش‌تنظیم فیلتر جدول"
        verbose_name_plural = "پیش‌تنظیمات فیلتر جداول"
        unique_together = ['user', 'table_name', 'name']
        ordering = ['table_name', 'name']
        indexes = [
            models.Index(fields=['table_name', 'user']),
            models.Index(fields=['table_name', 'is_public']),
        ]
    
    def __str__(self):
        return f"{self.table_name} - {self.name} ({self.user.username})"
    
    @property
    def filter_config(self):
        """بازگرداندن تنظیمات فیلتر"""
        try:
            return json.loads(self.filter_config_json) if self.filter_config_json else {}
        except json.JSONDecodeError:
            return {}
    
    @filter_config.setter
    def filter_config(self, value):
        """تنظیم تنظیمات فیلتر"""
        self.filter_config_json = json.dumps(value, ensure_ascii=False)


class TableFilterStats(models.Model):
    """مدل آمار استفاده از فیلترها"""
    
    table_name = models.CharField(max_length=100, verbose_name="نام جدول")
    column_id = models.CharField(max_length=100, verbose_name="شناسه ستون")
    filter_value = models.TextField(verbose_name="مقدار فیلتر")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    usage_count = models.PositiveIntegerField(default=1, verbose_name="تعداد استفاده")
    last_used = models.DateTimeField(auto_now=True, verbose_name="آخرین استفاده")
    
    class Meta:
        verbose_name = "آمار فیلتر جدول"
        verbose_name_plural = "آمار فیلترهای جداول"
        unique_together = ['table_name', 'column_id', 'filter_value', 'user']
        ordering = ['-usage_count', '-last_used']
        indexes = [
            models.Index(fields=['table_name', 'column_id']),
            models.Index(fields=['user', 'last_used']),
        ]
    
    def __str__(self):
        return f"{self.table_name}.{self.column_id}: {self.filter_value[:50]}"
    
    @classmethod
    def record_usage(cls, table_name, column_id, filter_value, user):
        """ثبت استفاده از فیلتر"""
        obj, created = cls.objects.get_or_create(
            table_name=table_name,
            column_id=column_id,
            filter_value=filter_value,
            user=user,
            defaults={'usage_count': 1}
        )
        if not created:
            obj.usage_count += 1
            obj.save(update_fields=['usage_count', 'last_used'])
        return obj
