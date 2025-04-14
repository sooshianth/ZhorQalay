from celery import shared_task
from django.utils import timezone
from .apis import process_sms_queue
from .models import SmsQueue
import logging

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
def debug_sms_task():
    """
    Simple task to verify Celery is working with SMS app
    """
    msg = "✅ SMS Queue Celery task is working!"
    logger.info(msg)
    return msg 