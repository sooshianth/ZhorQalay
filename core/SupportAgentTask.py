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

    def __str__(self):
        return self.description

    class Meta:
        verbose_name = "تسک کارشناس پشتیبانی"
        verbose_name_plural = "تسکهای کارشناس پشتیبانی"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class AdminTask(models.Model):
    """مدل تسک‌های مدیریت که از کارشناس پشتیبانی ارجاع می‌شوند"""
    referred_from_task = models.ForeignKey(SupportAgentTask, on_delete=models.CASCADE, verbose_name="تسک ارجاع شده")
    referred_from_agent = models.ForeignKey(SupportAgent, on_delete=models.CASCADE, verbose_name="کارشناس پشتیبانی ارجاع کننده")
    description = models.CharField(max_length=255, null=True, verbose_name="توضیحات", blank=True)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, null=True, blank=True, verbose_name="خرید")
    purchase_number = models.CharField(max_length=8, null=True, blank=True, verbose_name="شماره خرید")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, verbose_name="مشتری")
    phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name="شماره تلفن")
    feedback = models.CharField(max_length=255, null=True, blank=True, verbose_name="بازخورد")
    is_done = models.BooleanField(default=False, verbose_name="انجام شده")
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)
    urgency_level = models.IntegerField(null=True, blank=True, verbose_name="سطح اولویت")
    due_date = jmodels.jDateTimeField("تاریخ انجام", null=True, blank=True)
    admin_feedback = models.CharField(max_length=255, null=True, blank=True, verbose_name="بازخورد مدیریت")
    completed_at = jmodels.jDateTimeField("تاریخ تکمیل", null=True, blank=True)

    def __str__(self):
        return f"تسک مدیریت - {self.description}"

    class Meta:
        verbose_name = "تسک مدیریت"
        verbose_name_plural = "تسکهای مدیریت"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def create_from_support_task(cls, support_task, feedback=""):
        """ایجاد تسک مدیریت از تسک کارشناس پشتیبانی"""
        admin_task = cls.objects.create(
            referred_from_task=support_task,
            referred_from_agent=support_task.support_agent,
            description=support_task.description,
            purchase=support_task.purchase,
            purchase_number=support_task.purchase_number,
            customer=support_task.customer,
            phone_number=support_task.phone_number,
            feedback=feedback,
            urgency_level=support_task.urgency_level,
            due_date=support_task.due_date
        )
        return admin_task
