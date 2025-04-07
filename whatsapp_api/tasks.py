from celery import shared_task
from core._models import Customer
from .models import WhatsappNumber
from .utils import send_whatsapp_message

@shared_task
def send_weekly_whatsapp_messages():
    customers = Customer.objects.filter(whatsapp_preference=True)
    for customer in customers:
        send_whatsapp_message(customer)

@shared_task
def reset_daily_limits():
    WhatsappNumber.objects.update(sent_today=0)