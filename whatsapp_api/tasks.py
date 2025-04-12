from celery import shared_task
from core._models import Customer
from .models import WhatsappNumber
from .utils import send_whatsapp_message
from django.utils import timezone
import random
import time

@shared_task
def send_daily_whatsapp_messages():
    # دریافت مشتریانی که هنوز پیام این هفته را دریافت نکرده‌اند
    customers = Customer.objects.filter(
        whatsapp_preference=True,
        last_whatsapp_sent__lt=timezone.now() - timezone.timedelta(days=7)
    ).order_by('?')  # تصادفی کردن ترتیب برای توزیع بهتر
    
    for customer in customers:
        success = send_whatsapp_message(customer)
        if success:
            customer.last_whatsapp_sent = timezone.now()
            customer.save()
        else:
            # اگر ارسال ناموفق بود، کمی صبر می‌کنیم
            time.sleep(60)

@shared_task
def reset_daily_limits():
    WhatsappNumber.objects.update(sent_today=0)

@shared_task
def monitor_whatsapp_numbers():
    # بررسی سلامت شماره‌ها
    for number in WhatsappNumber.objects.all():
        if number.sent_today >= number.daily_limit:
            print(f"شماره {number.phone_number} به حد مجاز روزانه رسیده است")
        if not number.is_available_today():
            print(f"شماره {number.phone_number} امروز غیرفعال است")