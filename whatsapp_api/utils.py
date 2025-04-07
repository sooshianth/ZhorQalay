from django.template.loader import render_to_string
from django.utils import timezone
import pywhatkit as kit
import time
from core._models import CargoProduct, Customer
from .models import WhatsappNumber, WhatsappLog

def generate_message(customer):
    products = CargoProduct.objects.filter(stock__gt=0)
    product_list = "\n".join([f"➤ {p.name}: {p.price} تومان" for p in products])
    message = render_to_string("core/templates/whatsapp_template.txt", {
        "نام مشتری": customer.name,
        "لیست_کالاها": product_list,
    })
    return message

def send_whatsapp_message(customer):
    assigned_number = WhatsappNumber.objects.filter(is_active=True, sent_today__lt=models.F('daily_limit')).first()
    if not assigned_number:
        print("هیچ شماره WhatsApp فعالی با ظرفیت باقی‌مونده وجود ندارد!")
        return False

    message = generate_message(customer)
    to_number = customer.phone_number if customer.phone_number.startswith('+') else f'+98{customer.phone_number}'

    try:
        kit.sendwhatmsg_instantly(
            phone_no=to_number,
            message=message,
            wait_time=15,
            tab_close=True
        )
        time.sleep(5)  # تأخیر برای اطمینان از ارسال

        WhatsappLog.objects.create(
            recipient_number=to_number,
            message=message,
            sent_from=assigned_number
        )
        assigned_number.sent_today += 1
        assigned_number.messages_sent += 1
        assigned_number.save()
        return True
    except Exception as e:
        print(f"خطا در ارسال به {to_number}: {e}")
        return False