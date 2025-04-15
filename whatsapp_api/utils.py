from django.template.loader import render_to_string
from django.db import models
from django.db.models import F
from django.utils import timezone
import pywhatkit as kit
from core._models import CargoProduct, Customer
from .models import WhatsappNumber, WhatsappLog, WhatsappTemplate
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time

# در فایل utils.py
from django.template import Template, Context

def generate_message(customer, template_type, context=None):
    """
    تولید پیام بر اساس تمپلیت مشخص
    :param customer: شیء مشتری
    :param template_type: نوع تمپلیت (از TEMPLATE_TYPES)
    :param context: دیکشنری حاوی متغیرهای اضافی
    :return: متن پیام رندر شده
    """
    try:
        template = WhatsappTemplate.objects.get(template_type=template_type, is_active=True)
        
        # ایجاد context پیش‌فرض
        default_context = {
            'customer_name': customer.name,
            'customer_phone': customer.phone_number,
            'today': timezone.now().strftime("%Y-%m-%d"),
        }
        
        # ادغام با context ورودی
        if context:
            default_context.update(context)
        
        # رندر پیام
        message = Template(template.content).render(Context(default_context))
        return message
        
    except WhatsappTemplate.DoesNotExist:
        raise ValueError(f"تمپلیتی از نوع {template_type} یافت نشد")
    except Exception as e:
        raise ValueError(f"خطا در تولید پیام: {str(e)}")

def get_available_number():
    # اول شماره‌هایی که امروز فعال هستند و ظرفیت دارند را با اولویت بالاتر انتخاب می‌کنیم
    return WhatsappNumber.objects.filter(
        is_active=True,
        sent_today__lt=F('daily_limit')
    ).filter(
        working_days__contains=str(timezone.now().isoweekday())
    ).order_by('priority', 'sent_today').first()

def send_whatsapp_message(customer, template_type, context = None):
    assigned_number = get_available_number()
    if not assigned_number:
        print("هیچ شماره WhatsApp فعالی با ظرفیت باقی‌مونده برای امروز وجود ندارد!")
        return False

    try:
        message = generate_message(customer, template_type, context)
        assigned_number = get_available_number()
        
        if not assigned_number:
            raise ValueError("شماره واتساپ فعالی یافت نشد")
            
        # کدهای ارسال پیام (مانند قبل)
        to_number = customer.phone_number if customer.phone_number.startswith('+') else f'+98{customer.phone_number}'
        
        options = webdriver.ChromeOptions()
        options.add_argument(r"--user-data-dir=C:\Users\Asus\AppData\Local\Google\Chrome\User Data")
        options.add_argument(rf"--profile-directory={assigned_number.chrome_profile}")
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        whatsapp_url = f"https://web.whatsapp.com/send?phone={to_number}&text={message}"
        driver.get(whatsapp_url)
        print("صفحه واتس‌اپ باز شد، منتظر لود شدن...")

        # صبر تا وقتی که صفحه کامل لود بشه
        wait = WebDriverWait(driver, 30)
        
        # پیدا کردن فیلد پیام با XPath به‌روز
        message_input = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true" and @data-tab="10"]')))
        print("فیلدメッセージ پیدا شد.")

        # چک کردن متن فعلی
        current_text = message_input.text
        print(f"متن فعلی فیلد: {current_text}")

        # صبر اضافی برای لود کامل
        time.sleep(2)

        # ارسال با Enter
        message_input.send_keys(Keys.ENTER)
        print("Enter زده شد، پیام باید ارسال شده باشه.")

        time.sleep(2)  # صبر برای اطمینان از ارسال

        # ثبت لاگ و به‌روزرسانی
        WhatsappLog.objects.create(
            recipient_number=to_number,
            message=message,
            sent_from=assigned_number,
            template_type=template_type
        )
        assigned_number.sent_today = F('sent_today') + 1
        assigned_number.messages_sent = F('messages_sent') + 1
        assigned_number.save()

        driver.quit()
        return True
    except Exception as e:
        print(f"خطا در ارسال به {to_number}: {e}")
        # چاپ HTML صفحه برای دیباگ
        print("HTML صفحه:")
        print(driver.page_source[:1000])  # فقط 1000 کاراکتر اول برای خوانایی
        driver.quit()
        return False
