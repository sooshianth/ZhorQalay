from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class TaskCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام دسته‌بندی")
    color = models.CharField(max_length=20, default="#3498db", verbose_name="رنگ")
    icon = models.CharField(max_length=50, default="fa-tasks", verbose_name="آیکون")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "دسته‌بندی تسک"
        verbose_name_plural = "دسته‌بندی‌های تسک"

class ToDoItem(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('in_progress', 'در حال انجام'),
        ('completed', 'تکمیل شده'),
        ('deferred', 'به تعویق افتاده'),
        ('canceled', 'لغو شده'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'کم'),
        ('medium', 'متوسط'),
        ('high', 'زیاد'),
        ('urgent', 'فوری'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_items', verbose_name="کاربر")
    title = models.CharField(max_length=255, verbose_name="عنوان")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    is_completed = models.BooleanField(default=False, verbose_name="انجام شده")
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name="اولویت"
    )
    category = models.ForeignKey(
        TaskCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='tasks',
        verbose_name="دسته‌بندی"
    )
    color = models.CharField(max_length=20, blank=True, null=True, verbose_name="رنگ اختصاصی")
    tags = models.CharField(max_length=255, blank=True, null=True, verbose_name="برچسب‌ها")
    notes = models.TextField(blank=True, null=True, verbose_name="یادداشت‌های اضافی")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")
    due_date = models.DateField(blank=True, null=True, verbose_name="تاریخ سررسید")
    due_time = models.TimeField(blank=True, null=True, verbose_name="زمان سررسید")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="تاریخ تکمیل")
    
    remind_before = models.PositiveIntegerField(default=0, verbose_name="یادآوری قبل از سررسید (دقیقه)")
    
    class Meta:
        verbose_name = "تسک"
        verbose_name_plural = "تسک‌ها"
        ordering = ['-priority', 'due_date', 'due_time']

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Update is_completed based on status
        self.is_completed = self.status == 'completed'
        
        # Set completed_at when status changes to completed
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        # Clear completed_at if status is not completed
        elif self.status != 'completed':
            self.completed_at = None
            
        super().save(*args, **kwargs)
    
    def is_overdue(self):
        if not self.due_date:
            return False
        
        today = timezone.localdate()
        if self.due_date < today:
            return True
        
        if self.due_date == today and self.due_time:
            current_time = timezone.localtime().time()
            return self.due_time < current_time
            
        return False
    
    def get_tags_list(self):
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',')]

class TaskReminder(models.Model):
    task = models.ForeignKey(ToDoItem, on_delete=models.CASCADE, related_name='reminders')
    reminder_time = models.DateTimeField(verbose_name="زمان یادآوری")
    is_sent = models.BooleanField(default=False, verbose_name="ارسال شده")
    
    def __str__(self):
        return f"یادآوری برای {self.task.title}"
    
    class Meta:
        verbose_name = "یادآوری تسک"
        verbose_name_plural = "یادآوری‌های تسک"