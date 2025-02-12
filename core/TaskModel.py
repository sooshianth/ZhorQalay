from django.db import models
from django.utils import timezone

class Task(models.Model):
    purchase = models.ForeignKey('Purchase', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    description = models.TextField("توضیحات", blank=True, null=True)
    created_at = models.DateTimeField("تاریخ ثبت",default=timezone.now,editable=True)
    updated_at = models.DateTimeField("تاریخ بروزرسانی",auto_now=True)
    is_done = models.BooleanField("انجام شده", default=False)
    is_archived = models.BooleanField("آرشیو شده", default=False)

    class Meta:
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"
    
    def __str__(self):
        return self.title

    def change_is_done(self):
        temp = self.is_done
        self.is_done = not temp
    def change_is_archived(self):
        temp = self.is_archived
        self.is_archived = not temp