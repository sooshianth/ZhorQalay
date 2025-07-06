from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.PurchaseModel import Purchase, PurchaseStateChange
import logging

logger = logging.getLogger("core_purge_unpaid_purchases")

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
        
        logger.info(f"شروع حذف خریدهای پرداخت نشده قبل از {cutoff_date}")
        
        # پیدا کردن خریدهایی که در مرحله شروع شده یا پیامک ارسال شده یا تایید بازارگاه هستند
        # و بیش از تعداد روز مشخص شده از ایجاد آنها گذشته است
        purchases_to_delete = Purchase.objects.filter(
            state__in=['INITIATED', 'SMS_SENT', 'BAZAARGAH_CONFIRMED'],
            created_at__lt=cutoff_date
        )
        
        count = purchases_to_delete.count()
        
        if dry_run:
            logger.info(f"حالت آزمایشی: {count} خرید پرداخت نشده یافت شد که حذف نخواهند شد")
            for purchase in purchases_to_delete:
                logger.info(f"[آزمایشی] خرید {purchase.invoice_id} - {purchase.customer.name} - وضعیت: {purchase.get_state_display()} - تاریخ ایجاد: {purchase.created_at}")
        else:
            if count > 0:
                # ثبت لاگ قبل از حذف
                for purchase in purchases_to_delete:
                    logger.info(f"حذف خودکار خرید {purchase.invoice_id} - {purchase.customer.name} - وضعیت: {purchase.get_state_display()} - تاریخ ایجاد: {purchase.created_at}")
                
                # حذف خریدها
                purchases_to_delete.delete()
                
                logger.info(f"{count} خرید پرداخت نشده با موفقیت حذف شد")
            else:
                logger.info("هیچ خرید پرداخت نشده‌ای برای حذف یافت نشد")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"پایان عملیات حذف خودکار در {end_time} (زمان: {duration:.2f} ثانیه)") 