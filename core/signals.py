from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from core._models import Purchase, Task


@receiver(post_save, sender=Purchase)
def create_task_for_purchase(sender, instance, created, **kwargs):
    if created:  # فقط اگر Purchase جدید ایجاد شده باشد
        # ایجاد تسک برای ۱۵ دقیقه بعد
        due_date = timezone.now() + timedelta(minutes=15)
        
        # توضیحات تسک
        task_description = f"پیگیری پیامک ارسال شده برای مشتری {instance.customer.name} - کوتاژ {instance.cargo.cottage if instance.cargo else 'بدون کوتاژ'}"
        
        # ایجاد تسک
        Task.objects.create(
            description=task_description,
            customer=instance.customer,  # مشتری مرتبط با خرید
            purchase=instance,  # خرید مرتبط با تسک
            due_date=due_date,  # زمان انجام تسک (۱۵ دقیقه بعد)
            status=False  # تسک به‌صورت پیش‌فرض انجام نشده است
        )