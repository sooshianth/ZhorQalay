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
        'schedule': crontab(minute='*/1'),  # هر 1 دقیقه
        'args': (20,),  # اندازه هر دسته: 20 پیامک
    },
    
    # تسک جدید برای بررسی خریدهای بدون پیامک
    'check-purchases-for-sms': {
        'task': 'sms_api.tasks.check_and_send_purchase_sms_task',
        'schedule': crontab(minute='*/15'),  # هر 15 دقیقه
        'kwargs': {'hours_back': 4},  # بررسی خریدهای 4 ساعت اخیر
    },
    
    # 'retry-failed-sms': {
    #     'task': 'sms_api.tasks.retry_failed_sms_task',
    #     'schedule': crontab(hour='*/1'),  # هر 1 ساعت
    #     'kwargs': {'max_retries': 3, 'batch_size': 20},
    # },
    # 'purge-unpaid-purchases': {
    #     'task': 'core.tasks.tasks.purge_unpaid_purchases_task',
    #     'schedule': crontab(hour=2, minute=0),  # هر روز ساعت 2 صبح
    #     'kwargs': {'days': 1},  # خریدهای قدیمی‌تر از 1 روز حذف شوند
    # },
    'change-sales-agents-after-two-months-of-no-purchase': {
        'task': 'core.tasks.tasks.change_sales_agents_after_two_months_of_no_purchase',
        'schedule': crontab(hour=2, minute=0),  # هر روز ساعت 02:00
    },
    
    # تسک‌های جدید برای به‌روزرسانی خریدهای بازارگاه
    'update-purchases-last-24-hours': {
        'task': 'bki_api.tasks.update_purchases_last_24_hours',
        'schedule': crontab(minute='*/30'),  # هر 30 ثانیه
    },
    'update-purchases-last-week': {
        'task': 'bki_api.tasks.update_purchases_last_week',
        'schedule': crontab(minute=0, hour='*/2'),  # هر 2 ساعت
    },
    'update-purchases-last-month': {
        'task': 'bki_api.tasks.update_purchases_last_month',
        'schedule': crontab(minute=0, hour='*/4'),  # هر 4 ساعت
    },
    'update-purchases-all-time': {
        'task': 'bki_api.tasks.update_purchases_all_time',
        'schedule': crontab(minute=0, hour='*/8'),  # هر 8 ساعت
    },
}

app.autodiscover_tasks()