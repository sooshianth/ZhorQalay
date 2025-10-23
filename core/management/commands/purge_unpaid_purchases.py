from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.PurchaseModel import Purchase, PurchaseStateChange
import logging

logger = logging.getLogger("bugs")

class Command(BaseCommand):
    help = 'حذف خودکار خریدهایی که بعد از یک روز پرداخت نشده‌اند'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='تعداد روزهایی که پس از آن خریدهای پرداخت نشده حذف می‌شوند',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='نمایش خریدهایی که حذف خواهند شد بدون حذف واقعی',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        start_time = timezone.now()
        cutoff_date = start_time - timedelta(days=days)

        logger.debug(f"Cutoff date: {cutoff_date}")

        # پیدا کردن خریدهایی که در مرحله شروع شده یا پیامک ارسال شده یا تایید بازارگاه هستند
        # و بیش از تعداد روز مشخص شده از ایجاد آنها گذشته است
        purchases_to_delete = Purchase.objects.filter(
            state__in=['INITIATED', 'SMS_SENT', 'BAZAARGAH_CONFIRMED'],
            created_at__lt=cutoff_date
        )
        
        count = purchases_to_delete.count()
        
        if dry_run:
            logger.debug(f"Dry run: {count} unpaid purchases found; none will be deleted")
            for purchase in purchases_to_delete:
                logger.debug(f"[Dry run] Purchase {purchase.invoice_id} - {purchase.customer.name} - State: {purchase.get_state_display()} - Created at: {purchase.created_at}")
        else:
            if count > 0:
                # log before deletion
                for purchase in purchases_to_delete:
                    logger.debug(f"Deleting unpaid purchase {purchase.invoice_id} - {purchase.customer.name} - State: {purchase.get_state_display()} - Created at: {purchase.created_at}")
                
                # delete purchases
                purchases_to_delete.delete()
                
                logger.info(f"{count} unpaid purchases successfully deleted")
            else:
                logger.debug("No unpaid purchases found to delete")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        logger.debug(f"Purge operation finished at {end_time} (duration: {duration:.2f} seconds)")