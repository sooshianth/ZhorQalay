from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
from core.PurchaseModel import Purchase
from core.SupportAgentModel import SupportAgent
from core.SupportAgentTask import SupportAgentTask
from django.db.models import Q

logger = logging.getLogger("bugs")

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

    logger.debug(f"Deleting unpaid purchases older than {cutoff_date}")

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
            logger.debug(f"Auto-deleting purchase {purchase.invoice_id} - {purchase.customer.name} - state: {purchase.get_state_display()} - created_at: {purchase.created_at}")
        
        # delete purchases
        purchases_to_delete.delete()
        logger.info(f"Successfully deleted {count} unpaid purchases")
    else:
        logger.debug("No unpaid purchases found to delete")
    
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


@shared_task
def check_purchases_for_support_tasks():
    """
    بررسی خریدها و ایجاد تسک‌های پشتیبانی بر اساس شرایط مشخص‌شده
    """
    try:
        # دریافت تمام خریدهایی که تسک پشتیبانی برای آن‌ها ایجاد نشده است
        existing_task_purchases = SupportAgentTask.objects.filter(
            purchase__isnull=False
        ).values_list('purchase_id', flat=True)

        # 1. خریدهایی که بارنامه در کمتر از 3 روز صادر شده
        three_days_ago = timezone.now().date() - timedelta(days=3)
        purchases_with_fast_barnameh = Purchase.objects.filter(
            ~Q(id__in=existing_task_purchases),
            barnamehs__barnameh_date__gte=three_days_ago,
            created_at__date__lte=three_days_ago
        ).distinct()

        for purchase in purchases_with_fast_barnameh:
            create_support_task(
                purchase=purchase,
                description=f"خرید {purchase.purchase_number} با بارنامه سریع (کمتر از 3 روز). تماس با مشتری برای قدردانی.",
                urgency_level=6
            )

        # 2. خریدهایی که 7 روز گذشته ولی بارنامه ندارند
        seven_days_ago = timezone.now().date() - timedelta(days=7)
        purchases_without_barnameh = Purchase.objects.filter(
            ~Q(id__in=existing_task_purchases),
            created_at__date__lte=seven_days_ago,
            barnamehs__isnull=True
        ).distinct()

        for purchase in purchases_without_barnameh:
            create_support_task(
                purchase=purchase,
                description=f"خرید {purchase.purchase_number} بیش از 7 روز گذشته اما بارنامه‌ای ثبت نشده است. پیگیری لازم است.",
                urgency_level=5
            )

        # 3. خریدهایی با کسری بیش از 10 میلیون تومان
        purchases_with_large_extelaf = Purchase.objects.filter(
            ~Q(id__in=existing_task_purchases),
            extelaf_amount__gt=100000000
        ).distinct()

        for purchase in purchases_with_large_extelaf:
            create_support_task(
                purchase=purchase,
                description=f"خرید {purchase.purchase_number} دارای کسری بیش از 10 میلیون تومان است. پیگیری فوری لازم است.",
                urgency_level=4
            )

        logger.debug("Support tasks created successfully.")
    except Exception as e:
        logger.error(f"Error creating support tasks: {str(e)}")

def create_support_task(purchase, description, urgency_level):
    """
    ایجاد تسک پشتیبانی برای یک خرید
    """
    try:
        # انتخاب یک کارشناس پشتیبانی به‌صورت تصادفی یا بر اساس منطق خاص
        support_agent = SupportAgent.objects.order_by('?').first()
        if not support_agent:
            logger.warning("No support agent found.")
            return

        SupportAgentTask.objects.create(
            support_agent=support_agent,
            description=description,
            purchase=purchase,
            purchase_number=purchase.purchase_number,
            customer=purchase.customer,
            phone_number=purchase.bazaargah_phone_number or purchase.tahvil_phone_number,
            urgency_level=urgency_level,
            due_date=timezone.now() + timedelta(days=2)  # مهلت 2 روزه
        )
        logger.debug(f"Support task created for purchase {purchase.purchase_number} with priority {urgency_level}.")
    except Exception as e:
        logger.error(f"Error creating support task for purchase {purchase.purchase_number}: {str(e)}")