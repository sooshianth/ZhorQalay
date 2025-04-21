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
        'schedule': crontab(hour=16, minute= 41),
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
    'assign-customers': {
        'task': 'whatsapp_api.tasks.assign_customers_to_days',
        'schedule': crontab(hour=0, minute=5),  # هر روز ساعت 00:05
    },

    'process-sms-queue': {
        'task': 'sms_api.tasks.process_sms_queue_task',
        'schedule': crontab(minute='*/5'),  # هر 5 دقیقه
        'args': (20,),  # اندازه هر دسته: 20 پیامک
    },
    'retry-failed-sms': {
        'task': 'sms_api.tasks.retry_failed_sms_task',
        'schedule': crontab(hour='*/1'),  # هر 1 ساعت
        'kwargs': {'max_retries': 3, 'batch_size': 20},
    },
    'purge-unpaid-purchases': {
        'task': 'core.tasks.tasks.purge_unpaid_purchases_task',
        'schedule': crontab(hour=2, minute=0),  # هر روز ساعت 2 صبح
        'kwargs': {'days': 1},  # خریدهای قدیمی‌تر از 1 روز حذف شوند
    },
}

app.autodiscover_tasks()