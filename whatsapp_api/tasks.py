from celery import shared_task, app
from core._models import Customer
from .models import WhatsappNumber
from .utils import send_whatsapp_message
from django.utils import timezone
import random
import time
from django.db.models import Count

@shared_task
def assign_customers_to_days():
    """تقسیم مشتریان بین روزهای هفته"""
    from core._models import Customer
    
    # تعداد مشتریان در هر روز
    customers_per_day = Customer.objects.filter(
        whatsapp_preference=True
    ).count() // 7
    
    for day in range(1, 8):  # 1-7 برای روزهای هفته
        # انتخاب مشتریان بدون روز اختصاص داده شده
        customers = Customer.objects.filter(
            whatsapp_preference=True,
            day_of_week__isnull=True
        )[:customers_per_day]
        
        # اختصاص روز به مشتریان
        customers.update(day_of_week=day)
        print(f"📅 {customers.count()} مشتری به روز {day} اختصاص یافتند")

@shared_task
def send_daily_whatsapp_messages(test_mode=False):
    today = timezone.now().isoweekday()
    customers = Customer.objects.filter(
        whatsapp_day=today,
        whatsapp_consent=True
    ).exclude(
        last_whatsapp_sent__gt=timezone.now() - timezone.timedelta(days=7)
    )
    
    for customer in customers:
        try:
            # تعیین نوع پیام بر اساس شرایط
            if not customer.last_whatsapp_sent:
                template_type = 'WELCOME'
                context = {'product_link': 'https://example.com/products'}
            else:
                template_type = 'PROMOTION'
                context = {'discount_code': 'WELCOME10'}
            
            if not test_mode:
                send_whatsapp_message(customer, template_type, context)
                customer.last_whatsapp_sent = timezone.now()
                customer.save()
                
        except Exception as e:
            print(f"خطا در ارسال به {customer.phone_number}: {str(e)}")

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