from django.core.management.base import BaseCommand
from bki_barnameh.models.BarnamehModel import Barnameh
from django.db import transaction
import logging

logger = logging.getLogger('bki_barnameh_commands')

class Command(BaseCommand):
    help = 'همه بارنامه‌ها را یک بار save می‌کند تا متدهای مربوطه اجرا شوند'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط نمایش دهد بدون ذخیره',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # دریافت همه بارنامه‌ها
        barnamehs = Barnameh.objects.all()
        total_count = barnamehs.count()
        
        self.stdout.write(
            self.style.SUCCESS(f'تعداد کل بارنامه‌ها: {total_count}')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('حالت تست فعال است - هیچ تغییری ذخیره نمی‌شود')
            )
            return
        
        success_count = 0
        error_count = 0
        
        with transaction.atomic():
            for i, barnameh in enumerate(barnamehs, 1):
                try:
                    # نمایش پیشرفت
                    if i % 100 == 0:
                        self.stdout.write(f'پردازش بارنامه {i}/{total_count}')
                    
                    # save کردن بارنامه
                    barnameh.save()
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f'خطا در save کردن بارنامه {barnameh.id}: {str(e)}')
                    self.stdout.write(
                        self.style.ERROR(f'خطا در بارنامه {barnameh.id}: {str(e)}')
                    )
        
        # نمایش نتایج نهایی
        self.stdout.write(
            self.style.SUCCESS(
                f'عملیات تکمیل شد:\n'
                f'موفق: {success_count}\n'
                f'خطا: {error_count}\n'
                f'کل: {total_count}'
            )
        )
