from celery import shared_task
from django.utils import timezone
from .apis import process_sms_queue, send_purchase_status_notification
from .models import SmsQueue, SmsTemplate
from core.PurchaseModel import Purchase, PurchaseStateChange
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

@shared_task
def process_sms_queue_task(batch_size=20):
    """
    Process pending SMS messages in the queue
    This task is scheduled to run periodically via Celery Beat
    """
    start_time = timezone.now()
    logger.info(f"Started SMS queue processing at {start_time}")
    
    try:
        results = process_sms_queue(batch_size=batch_size)
        
        # Log results summary
        sent_count = sum(1 for r in results if r.get('status') == 'sent')
        failed_count = sum(1 for r in results if r.get('status') == 'failed')
        
        summary = f"Processed {len(results)} SMS messages: {sent_count} sent, {failed_count} failed"
        logger.info(summary)
        
        # Log individual failures
        for result in results:
            if result.get('status') == 'failed':
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"Failed to send SMS ID {result.get('id')}: {error_msg}")
        
        return summary
    
    except Exception as e:
        error_message = f"Error processing SMS queue: {str(e)}"
        logger.exception(error_message)
        return error_message
    
    finally:
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Finished SMS queue processing at {end_time} (took {duration:.2f} seconds)")

@shared_task
def retry_failed_sms_task(max_retries=3, batch_size=20):
    """
    Retry failed SMS messages
    """
    logger.info(f"Starting retry for failed SMS messages")
    
    # Query for failed messages
    query = SmsQueue.objects.filter(
        status='failed',
        retry_count__lt=max_retries
    )
    
    count = query.count()
    
    if count == 0:
        logger.info("No failed SMS messages to retry")
        return "No messages to retry"
    
    logger.info(f"Found {count} failed SMS messages to retry")
    
    # Update status to pending
    query.update(status='pending')
    
    # Process the queue
    results = process_sms_queue(batch_size=batch_size)
    
    # Show results summary
    sent_count = sum(1 for r in results if r.get('status') == 'sent')
    failed_count = sum(1 for r in results if r.get('status') == 'failed')
    
    summary = f"Retried {len(results)} SMS messages: {sent_count} sent, {failed_count} failed"
    logger.info(summary)
    
    return summary

@shared_task
def check_and_send_purchase_sms_task(hours_back=24):
    """
    بررسی خریدهایی که در بازه زمانی مشخص ایجاد یا به‌روزرسانی شده‌اند اما پیامک دریافت نکرده‌اند
    این تسک برای مواردی است که خریدها از طریق آپلود فایل یا API ایجاد می‌شوند
    
    Args:
        hours_back (int): بررسی خریدهای چند ساعت اخیر
    """
    logger.info(f"Starting check for purchases without SMS notifications (last {hours_back} hours)")
    
    # زمان شروع بازه بررسی
    start_time = timezone.now() - timedelta(hours=hours_back)
    
    # یافتن خریدهایی که در بازه زمانی مشخص ایجاد یا به‌روزرسانی شده‌اند
    recent_purchases = Purchase.objects.filter(
        updated_at__gte=start_time
    )
    
    logger.info(f"Found {recent_purchases.count()} purchases updated in the last {hours_back} hours")
    
    sms_sent_count = 0
    
    for purchase in recent_purchases:
        # اگر مشتری وجود ندارد یا تنظیمات sms_preference غیرفعال است، پیامک ارسال نمی‌شود
        if not purchase.customer or not purchase.customer.sms_preference:
            continue
            
        # بررسی اینکه کارشناسان فروش مشتری فقط ادمین‌ها نباشند
        sales_agents = purchase.customer.sales_agent.all()
        has_non_admin = False
        for agent in sales_agents:
            if not agent.user.is_superuser:
                has_non_admin = True
                break
        
        if not has_non_admin:
            continue
            
        # بررسی آیا برای وضعیت فعلی این خرید پیامکی ارسال شده یا نه
        state_change = PurchaseStateChange.objects.filter(
            purchase=purchase,
            new_state=purchase.state,
            sms_sent=True
        ).exists()
        
        if state_change:
            # پیامک قبلاً ارسال شده است
            continue
            
        # بررسی آیا قالب فعال برای این وضعیت وجود دارد
        template = SmsTemplate.objects.filter(status=purchase.state, is_active=True).first()
        if not template:
            logger.warning(f"No active template found for state {purchase.state} (Purchase ID: {purchase.id})")
            continue
            
        # ارسال پیامک
        try:
            result = send_purchase_status_notification(purchase)
            if result:
                sms_sent_count += 1
                # ثبت ارسال پیامک
                PurchaseStateChange.objects.filter(
                    purchase=purchase,
                    new_state=purchase.state
                ).update(sms_sent=True, sms_sent_at=timezone.now())
                
                # اگر رکورد تغییر وضعیت وجود نداشت، یکی ایجاد کنیم
                if not PurchaseStateChange.objects.filter(purchase=purchase, new_state=purchase.state).exists():
                    PurchaseStateChange.objects.create(
                        purchase=purchase,
                        previous_state=purchase.state,  # در اینجا وضعیت قبلی را نمی‌دانیم
                        new_state=purchase.state,
                        sms_sent=True,
                        sms_sent_at=timezone.now(),
                        notes="ارسال پیامک خودکار توسط تسک Celery"
                    )
        except Exception as e:
            logger.error(f"Error sending SMS for purchase {purchase.id}: {str(e)}")
    
    summary = f"Sent {sms_sent_count} SMS notifications for purchases without previous notifications"
    logger.info(summary)
    return summary

@shared_task
def debug_sms_task():
    """
    Simple task to verify Celery is working with SMS app
    """
    msg = "✅ SMS Queue Celery task is working!"
    logger.info(msg)
    return msg 