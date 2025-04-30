.. _installation:

راهنمای نصب و راه‌اندازی
====================

در این بخش، مراحل نصب و راه‌اندازی پروژه کانقالای توضیح داده شده است.

.. toctree::
   :maxdepth: 2

   requirements
   installation
   configuration
   running

پیش‌نیازها
-------

برای نصب و راه‌اندازی پروژه کانقالای، نیاز به موارد زیر دارید:

* پایتون 3.8 یا بالاتر
* Redis
* SQLite (یا دیگر پایگاه داده‌های پشتیبانی شده توسط Django)
* pip (برای نصب وابستگی‌ها)

مراحل نصب
-------

1. **کلون کردن مخزن پروژه**

   ابتدا مخزن پروژه را از گیت‌هاب کلون کنید:

   .. code-block:: bash

       git clone https://github.com/your-username/kunqalay.git
       cd kunqalay

2. **ایجاد محیط مجازی پایتون**

   برای جلوگیری از تداخل با دیگر پروژه‌ها، توصیه می‌شود یک محیط مجازی ایجاد کنید:

   .. code-block:: bash

       python -m venv venv
       # در ویندوز
       venv\Scripts\activate
       # در لینوکس/مک
       source venv/bin/activate

3. **نصب وابستگی‌ها**

   با استفاده از pip، وابستگی‌های پروژه را نصب کنید:

   .. code-block:: bash

       pip install -r requirements.txt

4. **اجرای مهاجرت‌های پایگاه داده**

   پایگاه داده را با اجرای دستورات مهاجرت ایجاد کنید:

   .. code-block:: bash

       python manage.py migrate

5. **ایجاد کاربر مدیر**

   یک کاربر مدیر برای پنل ادمین ایجاد کنید:

   .. code-block:: bash

       python manage.py createsuperuser

پیکربندی
------

پیش از راه‌اندازی پروژه، نیاز به پیکربندی برخی تنظیمات دارید:

1. **تنظیمات پایگاه داده**

   در فایل settings.py، تنظیمات پایگاه داده را بر اساس محیط خود تنظیم کنید:

   .. code-block:: python

       DATABASES = {
           'default': {
               'ENGINE': 'django.db.backends.sqlite3',
               'NAME': BASE_DIR / 'db.sqlite3',
           }
       }

2. **تنظیمات Redis**

   برای استفاده از Celery و Django Channels، نیاز به تنظیم Redis دارید:

   .. code-block:: python

       CELERY_BROKER_URL = 'redis://localhost:6379/0'
       CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

       CHANNEL_LAYERS = {
           'default': {
               'BACKEND': 'channels_redis.core.RedisChannelLayer',
               'CONFIG': {
                   "hosts": [('127.0.0.1', 6379)],
               },
           },
       }

3. **تنظیمات API های خارجی**

   برای استفاده از API های واتساپ و پیامک، تنظیمات مربوطه را در settings.py وارد کنید:

   .. code-block:: python

       # تنظیمات واتساپ
       WHATSAPP_API_KEY = "your_api_key"
       WHATSAPP_API_SECRET = "your_api_secret"

       # تنظیمات پیامک
       SMS_API_KEY = "your_sms_api_key"
       SMS_API_SECRET = "your_sms_api_secret"

راه‌اندازی پروژه
------------

پس از نصب و پیکربندی، می‌توانید پروژه را راه‌اندازی کنید:

1. **اجرای سرور توسعه**

   .. code-block:: bash

       python manage.py runserver

   سرور در آدرس http://localhost:8000 در دسترس خواهد بود.

2. **اجرای Celery**

   برای اجرای وظایف غیرهمزمان، Celery را اجرا کنید:

   .. code-block:: bash

       celery -A config worker -l info

3. **اجرای Celery Beat**

   برای اجرای وظایف زمان‌بندی شده، Celery Beat را اجرا کنید:

   .. code-block:: bash

       celery -A config beat -l info

4. **دسترسی به پنل ادمین**

   با مراجعه به آدرس http://localhost:8000/ewdfsrgtyuiougyjgtrdthugghuji/ و وارد کردن نام کاربری و رمز عبور کاربر مدیر، می‌توانید به پنل ادمین دسترسی پیدا کنید.

عیب‌یابی متداول
-----------

* **خطای اتصال به Redis**: اطمینان حاصل کنید که سرویس Redis در حال اجرا است.
* **خطای اجرای مهاجرت‌ها**: اطمینان حاصل کنید که پایگاه داده به درستی پیکربندی شده است.
* **خطای نصب وابستگی‌ها**: اطمینان حاصل کنید که از نسخه صحیح پایتون استفاده می‌کنید. 