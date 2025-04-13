import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')

# تنظیمات زمان‌بندی
app.conf.beat_schedule = {
    'send_daily_messages': {
        'task': 'whatsapp_api.tasks.send_daily_whatsapp_messages',
        'schedule': crontab(hour=16, minute= 41),  # ساعت 16:10 (4:10 بعدازظهر)
        'kwargs': {'test_mode': True}  # فعال کردن حالت تست
    },    
    'reset-daily-limits': {
        'task': 'whatsapp_api.tasks.reset_daily_limits',
        'schedule': crontab(hour=0, minute=0),  # هر روز نیمه‌شب
    },
    'monitor-numbers': {
        'task': 'whatsapp_api.tasks.monitor_whatsapp_numbers',
        'schedule': crontab(minute='*/30'),  # هر 30 دقیقه
    },
}

app.autodiscover_tasks()