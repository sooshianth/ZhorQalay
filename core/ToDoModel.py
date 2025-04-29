from django.db import models
from django.contrib.auth.models import User

class ToDoItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_items')
    title = models.CharField(max_length=255, verbose_name="عنوان")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")
    is_completed = models.BooleanField(default=False, verbose_name="انجام شده")
    priority = models.CharField(
        max_length=10,
        choices=[('low', 'کم'), ('medium', 'متوسط'), ('high', 'زیاد')],
        default='medium',
        verbose_name="اولویت"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    due_date = models.DateTimeField(blank=True, null=True, verbose_name="تاریخ سررسید")

    def __str__(self):
        return self.title