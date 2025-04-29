from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from core._models import Purchase, Task, SalesAgent
from django.db import models


@receiver(post_save, sender=Purchase)
def create_task_for_purchase(sender, instance, created, **kwargs):
    if created:  # فقط اگر Purchase جدید ایجاد شده باشد
        # ایجاد تسک برای ۱۵ دقیقه بعد
        due_date = timezone.now() + timedelta(minutes=15)
        
        # توضیحات تسک
        task_description = f"پیگیری پیامک ارسال شده برای مشتری - کوتاژ {instance.cargo if instance.cargo else 'بدون کوتاژ'}"
        
        # ایجاد تسک
        # چک کردن اینکه آیا کارشناسان فروش مشتری فقط ادمین‌ها هستند یا نه
        sales_agents = instance.customer.sales_agent.all()
        has_non_admin = False
        for agent in sales_agents:
            if not agent.user.is_superuser:
                has_non_admin = True
                break
        
        if has_non_admin:
            Task.objects.create(
                description=task_description,
                customer=instance.customer,  # مشتری مرتبط با خرید
                purchase=instance,  # خرید مرتبط با تسک
                due_date=due_date,  # زمان انجام تسک (۱۵ دقیقه بعد)
                status=False  # تسک به‌صورت پیش‌فرض انجام نشده است
            )

from django.db.models.signals import post_save
from django.dispatch import receiver
from core._models import WeeklyAttendance, MonthlyAttendance
from django.utils.timezone import now

@receiver(post_save, sender=WeeklyAttendance)
def update_monthly_attendance(sender, instance, **kwargs):
    month = instance.week_start_date.strftime('%Y-%m')  # استخراج ماه از تاریخ شروع هفته
    monthly_attendance, created = MonthlyAttendance.objects.get_or_create(
        employee=instance.employee,
        month=month
    )
    # جمع‌آوری مجموع ساعات هفتگی
    total_hours = WeeklyAttendance.objects.filter(
        employee=instance.employee,
        week_start_date__month=instance.week_start_date.month
    ).aggregate(models.Sum('total_hours'))['total_hours__sum'] or 0
    monthly_attendance.total_hours = total_hours
    monthly_attendance.save()