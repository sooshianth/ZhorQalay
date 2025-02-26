from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from .PurchaseModel import Purchase
from .CustomerModel import Customer
from .NotificationModel import Notification

class Task(models.Model):
    TASK_STATUS = [
        (True, 'انجام شده'),
        (False, 'انجام نشده'),
    ]

    description = models.TextField(_('توضیحات'), max_length=100)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name=_('مشتری'), related_name='tasks')
    status = models.BooleanField(_('وضعیت پیگیری'), choices=TASK_STATUS, default=False)
    create_time = jmodels.jDateTimeField(_('زمان ایجاد شده'), auto_now_add=True)
    due_date = jmodels.jDateTimeField(_('زمان مورد انتظار پیگیری'), null=True, blank=True)

    class Meta:
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # بررسی می‌کنه که آیا این تسک جدید است
        super().save(*args, **kwargs)

        if is_new:
            # ارسال نوتیفیکیشن به کارشناس فروش
            Notification.objects.create(
                user=self.customer.sales_agent.user,  
                message=f"یک تسک جدید برای مشتری {self.customer.name} ایجاد شد."
            )
    
    def __str__(self):
        return f"{self.customer.name}"

    def set_auto_update(self):
        self.auto_follow_up_date = self.created_at + timedelta(minutes=15)

    def change_status(self):
        if self.status:
            self.mark_as_not_done()
        else:
            self.mark_as_done()

    def mark_as_done(self):
        self.status = True
        self.save()

    def mark_as_not_done(self):
        self.status = False
        self.save()
