from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from .PurchaseModel import Purchase
from .CustomerModel import Customer

class Task(models.Model):

    TASK_STATUS = [
        {True,'انجام شده'},
        {False,'انجام نشده'},
    ]

    decription = models.TextField(_('توضیحات'), max_length=100)
    purchase = models.ForeignKey(Purchase, null=True, blank=True, related_name='tasks')
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name=_('مشتری'), related_name='tasks')
    sales_agent = customer.sales_agent
    status = models.BooleanField(_('وضعیت پیگیری'), choices=TASK_STATUS, default=False)
    create_time = models.DateTimeField(_('زمان ایجاد شده'), auto_now_add=True)
    due_date = models.DateTimeField(_('زمان مورد انتظار پیگیری'), null=True, blank=True)

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