from django.db import models
from .SupportAgentModel import SupportAgent
from .PurchaseModel import Purchase
from .CustomerModel import Customer
from django_jalali.db import models as jmodels

class SupportAgentTask(models.Model):
    support_agent = models.ForeignKey(SupportAgent, on_delete=models.CASCADE, null=True, verbose_name="کارشناس پشتیبانی")
    description = models.CharField(max_length=255, null=True, verbose_name="توضیحات", blank=True)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, null=True, blank=True, verbose_name="خرید")
    purchase_number = models.CharField(max_length=8, null=True, blank=True, verbose_name="شماره خرید")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, verbose_name="مشتری")
    phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name="شماره تلفن")
    feedback = models.CharField(max_length=255, null=True, blank=True, verbose_name="بازخورد")
    is_done = models.BooleanField(default=False, verbose_name="انجام شده")
    is_on_admin = models.BooleanField(default=False, verbose_name="در انتظار مدیر")
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)
    urgency_level = models.IntegerField(null=True, blank=True, verbose_name="سطح اولویت")
    due_date = jmodels.jDateTimeField("تاریخ انجام", null=True, blank=True)

    def _str_(self):
        return self.description

    class Meta:
        verbose_name = "تسک کارشناس پشتیبانی"
        verbose_name_plural = "تسکهای کارشناس پشتیبانی"

    def save(self,*args,**kwargs):
        if self.due_date:
            self.due_date = jmodels.jDateTimeField(self.due_date)
        super().save(*args,**kwargs)
