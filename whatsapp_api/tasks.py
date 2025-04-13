from celery import shared_task
from core._models import Customer
from .models import WhatsappNumber
from .utils import send_whatsapp_message
from django.utils import timezone
import random
import time

@shared_task
def send_daily_whatsapp_messages(test_mode=False):
    if test_mode:
        print("🔥 حالت تست فعال شد - بررسی زمان‌بندی")
    
    customers = Customer.objects.filter(
        whatsapp_preference=True,
    ).order_by('?')
    
    if test_mode:
        customers = customers[:3]  # فقط 3 مشتری برای تست
        print(f"🔍 تعداد مشتریان برای تست: {customers.count()}")
    
    for customer in customers:
        try:
            send_single_message.apply_async(
                args=[customer.id],
                countdown=120 if not test_mode else 10  # تاخیر کمتر در حالت تست
            )
            if test_mode:
                print(f"✉️ پیام تست برای {customer.phone_number} زمان‌بندی شد")
        except Exception as e:
            print(f"خطا: {e}")
@shared_task
def send_single_message(customer_id):
    customer = Customer.objects.get(id=customer_id)
    success = send_whatsapp_message(customer)
    if success:
        customer.last_whatsapp_sent = timezone.now()
        customer.save()

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

@shared_task
def debug_task():
    print("✅ تست Celery موفقیت‌آمیز بود!")
    return "OK"