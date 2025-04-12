import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')

# اضافه کردن تنظیمات زمان‌بندی
app.conf.beat_schedule = {
    'reset-daily-limits': {
        'task': 'whatsapp_api.tasks.reset_daily_limits',
        'schedule': crontab(hour=0, minute=0),  # هر روز نیمه شب
    },
    'send-daily-messages': {
        'task': 'whatsapp_api.tasks.send_daily_whatsapp_messages',
        'schedule': crontab(hour=9, minute=0),  # هر روز ساعت 9 صبح
    },
    'monitor-numbers': {
        'task': 'whatsapp_api.tasks.monitor_whatsapp_numbers',
        'schedule': crontab(minute='*/30'),  # هر 30 دقیقه
    },
}

app.autodiscover_tasks()