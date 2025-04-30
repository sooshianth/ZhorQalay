.. _whatsapp_api_module:

ماژول WhatsApp API
===============

ماژول WhatsApp API برای ارسال و دریافت پیام‌های واتساپ طراحی شده است. این ماژول با API واتساپ یکپارچه‌سازی شده و امکان ارسال پیام به مشتریان و دریافت پاسخ آن‌ها را فراهم می‌کند.

مدل‌های اصلی
---------

مدل WhatsAppMessage
~~~~~~~~~~~~~~~~

مدل WhatsAppMessage برای نگهداری اطلاعات پیام‌های واتساپ طراحی شده است.

**فیلدهای اصلی**:

* **sender**: فرستنده پیام
* **recipient**: گیرنده پیام
* **message**: متن پیام
* **media_url**: آدرس محتوای چندرسانه‌ای
* **media_type**: نوع محتوای چندرسانه‌ای
* **status**: وضعیت پیام
* **message_id**: شناسه پیام در واتساپ
* **customer**: ارتباط با مشتری
* **sales_agent**: ارتباط با کارشناس فروش
* **sent_at**: تاریخ ارسال
* **received_at**: تاریخ دریافت
* **created_at**: تاریخ ثبت
* **updated_at**: تاریخ بروزرسانی

مدل WhatsAppTemplate
~~~~~~~~~~~~~~~~~

مدل WhatsAppTemplate برای نگهداری اطلاعات قالب‌های پیام واتساپ طراحی شده است.

**فیلدهای اصلی**:

* **name**: نام قالب
* **type**: نوع قالب
* **category**: دسته‌بندی قالب
* **components**: اجزای قالب
* **language**: زبان قالب
* **status**: وضعیت قالب
* **created_at**: تاریخ ثبت
* **updated_at**: تاریخ بروزرسانی

مدل WhatsAppAccount
~~~~~~~~~~~~~~~~

مدل WhatsAppAccount برای نگهداری اطلاعات حساب‌های واتساپ طراحی شده است.

**فیلدهای اصلی**:

* **phone_number**: شماره تلفن
* **business_name**: نام کسب و کار
* **api_key**: کلید API
* **api_secret**: رمز API
* **webhook_url**: آدرس وب‌هوک
* **status**: وضعیت حساب
* **created_at**: تاریخ ثبت
* **updated_at**: تاریخ بروزرسانی

توابع اصلی
--------

تابع send_whatsapp_message
~~~~~~~~~~~~~~~~~~~~~~~

این تابع برای ارسال پیام واتساپ استفاده می‌شود.

**پارامترها**:

* **to**: شماره تلفن گیرنده
* **message**: متن پیام
* **media_url**: آدرس محتوای چندرسانه‌ای (اختیاری)
* **media_type**: نوع محتوای چندرسانه‌ای (اختیاری)
* **customer_id**: شناسه مشتری (اختیاری)
* **sales_agent_id**: شناسه کارشناس فروش (اختیاری)

**مثال استفاده**:

.. code-block:: python

    from whatsapp_api.utils import send_whatsapp_message
    
    send_whatsapp_message(
        to="989123456789",
        message="سلام، خوش آمدید!",
        customer_id=1
    )

تابع send_whatsapp_template
~~~~~~~~~~~~~~~~~~~~~~~~

این تابع برای ارسال پیام واتساپ با استفاده از قالب استفاده می‌شود.

**پارامترها**:

* **to**: شماره تلفن گیرنده
* **template_name**: نام قالب
* **template_params**: پارامترهای قالب
* **customer_id**: شناسه مشتری (اختیاری)
* **sales_agent_id**: شناسه کارشناس فروش (اختیاری)

**مثال استفاده**:

.. code-block:: python

    from whatsapp_api.utils import send_whatsapp_template
    
    send_whatsapp_template(
        to="989123456789",
        template_name="welcome_message",
        template_params={"name": "علی", "company": "کانقالای"},
        customer_id=1
    )

وظایف Celery
---------

وظیفه send_bulk_whatsapp_messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

این وظیفه برای ارسال پیام واتساپ به صورت انبوه استفاده می‌شود.

**پارامترها**:

* **numbers**: لیست شماره تلفن‌ها
* **message**: متن پیام
* **media_url**: آدرس محتوای چندرسانه‌ای (اختیاری)
* **media_type**: نوع محتوای چندرسانه‌ای (اختیاری)

**مثال استفاده**:

.. code-block:: python

    from whatsapp_api.tasks import send_bulk_whatsapp_messages
    
    send_bulk_whatsapp_messages.delay(
        numbers=["989123456789", "989123456788"],
        message="سلام، خوش آمدید!"
    )

وظیفه process_whatsapp_webhook
~~~~~~~~~~~~~~~~~~~~~~~~~~~

این وظیفه برای پردازش وب‌هوک‌های واتساپ استفاده می‌شود.

**پارامترها**:

* **data**: داده‌های وب‌هوک

**مثال استفاده**:

.. code-block:: python

    from whatsapp_api.tasks import process_whatsapp_webhook
    
    process_whatsapp_webhook.delay(data=webhook_data)

تنظیم و پیکربندی
-------------

برای استفاده از ماژول WhatsApp API، نیاز به تنظیم موارد زیر است:

1. ثبت‌نام در سرویس واتساپ بیزینس API
2. دریافت کلید API
3. تنظیم وب‌هوک
4. تنظیم قالب‌های پیام

**مثال تنظیمات در فایل settings.py**:

.. code-block:: python

    # تنظیمات واتساپ
    WHATSAPP_API_KEY = "your_api_key"
    WHATSAPP_API_SECRET = "your_api_secret"
    WHATSAPP_PHONE_NUMBER = "your_phone_number"
    WHATSAPP_WEBHOOK_URL = "your_webhook_url"

API Endpoints
-----------

ماژول WhatsApp API چندین API endpoint برای ارسال و دریافت پیام‌های واتساپ فراهم می‌کند:

* **/whatsapp/send/**: ارسال پیام واتساپ
* **/whatsapp/send-template/**: ارسال پیام واتساپ با استفاده از قالب
* **/whatsapp/webhook/**: دریافت وب‌هوک‌های واتساپ
* **/whatsapp/messages/**: دریافت لیست پیام‌های واتساپ
* **/whatsapp/templates/**: دریافت لیست قالب‌های واتساپ

داشبورد
------

ماژول WhatsApp API دارای یک داشبورد برای مدیریت پیام‌های واتساپ است. این داشبورد در آدرس زیر قابل دسترسی است:

.. code-block:: text

    /whatsapp/dashboard/

در این داشبورد، امکانات زیر فراهم شده است:

* مشاهده لیست پیام‌های ارسالی و دریافتی
* ارسال پیام جدید
* ارسال پیام انبوه
* مدیریت قالب‌های پیام
* مشاهده گزارش‌های ارسال پیام 