from django.db import models
from django.core.exceptions import ValidationError
from datetime import timedelta
from . import PurchaseModel
from . import CustomerModel

class Task(models.Model):

    TASK_STATUS = [
        {True,'انجام شده'},
        {False,'انجام نشده'},
    ]

    title = models.CharField(_('عنوان'), max_length=20)
    purchase = models.ForeignKey(PurchaseModel, null=True, blank=True, related_name='tasks')
    customer = models.ForeignKey(CustomerModel, on_delete=models.CASCADE)
    decription = models.TextField(_('توضیحات'), max_length=100)
    status = models.BooleanField(_('وضعیت پیگیری'), choices=TASK_STATUS, default=False)
    create_time = models.DateTimeField(_('زمان ایجاد شده'), auto_now_add=True)
    auto_update_time = models.DateTimeField(_('زمان پیگیری خودکار'), auto_now=True)

    class Meta:
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"

    def __str__(self):
        return f"{self.title} - {self.customer.name}"
 
    def set_auto_update(self):
        self.auto_follow_up_date = self.created_at + timedelta(minutes=15) 

    def mark_as_done(self):
        self.status = True
        self.save()

    def mark_as_not_done(self):
        self.status = False
        self.save()