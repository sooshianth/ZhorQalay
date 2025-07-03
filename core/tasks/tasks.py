from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
from core.PurchaseModel import Purchase

logger = logging.getLogger("core_tasks")

@shared_task
def purge_unpaid_purchases_task(days=1):
    """
    تسک سلری برای حذف خودکار خریدهای پرداخت نشده
    
    Args:
        days (int): تعداد روزهایی که پس از آن خریدهای پرداخت نشده حذف می‌شوند
    
    Returns:
        dict: نتیجه عملیات حذف
    """
    start_time = timezone.now()
    cutoff_date = start_time - timedelta(days=days)
    
    logger.info(f"شروع حذف خودکار خریدهای پرداخت نشده قبل از {cutoff_date}")
    
    # پیدا کردن خریدهایی که در مرحله شروع شده یا پیامک ارسال شده یا تایید بازارگاه هستند
    # و بیش از تعداد روز مشخص شده از ایجاد آنها گذشته است
    purchases_to_delete = Purchase.objects.filter(
        state__in=['INITIATED', 'SMS_SENT', 'BAZAARGAH_CONFIRMED'],
        created_at__lt=cutoff_date
    )
    
    count = purchases_to_delete.count()
    deleted_purchases = []
    
    if count > 0:
        # ثبت لاگ قبل از حذف
        for purchase in purchases_to_delete:
            purchase_info = {
                'invoice_id': purchase.invoice_id,
                'customer_name': purchase.customer.name,
                'state': purchase.get_state_display(),
                'created_at': str(purchase.created_at)
            }
            deleted_purchases.append(purchase_info)
            logger.info(f"حذف خودکار خرید {purchase.invoice_id} - {purchase.customer.name} - وضعیت: {purchase.get_state_display()} - تاریخ ایجاد: {purchase.created_at}")
        
        # حذف خریدها
        purchases_to_delete.delete()
        logger.info(f"{count} خرید پرداخت نشده با موفقیت حذف شد")
    else:
        logger.info("هیچ خرید پرداخت نشده‌ای برای حذف یافت نشد")
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    return {
        'status': 'success',
        'deleted_count': count,
        'deleted_purchases': deleted_purchases,
        'start_time': str(start_time),
        'end_time': str(end_time),
        'duration_seconds': duration
    } 


from core.CustomerModel import Customer

@shared_task
def change_sales_agents_after_two_months_of_no_purchase():
    """
    Change the sales agent for customers after two months of no purchase.
    """
    customers = Customer.objects.filter(purchases_made__isnull=False)
    for customer in customers:
        customer.change_sales_agents_after_two_months_of_no_purchase()
