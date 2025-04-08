from django.template.loader import render_to_string
from django.db import models
from django.db.models import F
from django.utils import timezone
import pywhatkit as kit
import time
from core._models import CargoProduct, Customer
from .models import WhatsappNumber, WhatsappLog
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def generate_message(customer):
    products = CargoProduct.objects.all()
    product_list = "\n".join([f"➤ {p.product_type}: {p.customer_price} تومان" for p in products])
    message = render_to_string("whatsapp_api/whatsapp_template.txt", {
        "name": customer.name,  # تغییر به نام_مشتری
        "list": product_list,  # بدون تغییر
    })
    return message

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time

def send_whatsapp_message(customer):
    assigned_number = WhatsappNumber.objects.filter(is_active=True, sent_today__lt=F('daily_limit')).first()
    if not assigned_number:
        print("هیچ شماره WhatsApp فعالی با ظرفیت باقی‌مونده وجود ندارد!")
        return False

    message = generate_message(customer)
    to_number = customer.phone_number if customer.phone_number.startswith('+') else f'+98{customer.phone_number}'

    try:
        # تنظیمات کروم با پروفایل
        options = webdriver.ChromeOptions()
        options.add_argument(r"--user-data-dir=C:\Users\Asus\AppData\Local\Google\Chrome\User Data")
        options.add_argument(r"--profile-directory=Profile 4")
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        # باز کردن لینک مستقیم واتس‌اپ
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
            sent_from=assigned_number
        )
        assigned_number.sent_today += 1
        assigned_number.messages_sent += 1
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
