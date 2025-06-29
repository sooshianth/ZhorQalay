from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from fledger.models import Wallet, LedgerEntry
from core.PurchaseModel import Purchase
from core.CargoProductModel import VaredKonandeh


class Command(BaseCommand):
    help = 'همگام‌سازی کیف پول‌های واردکنندگان با خریدهای موجود'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='اجبار به بازنویسی کیف پول‌های موجود',
        )
        parser.add_argument(
            '--varedkonandeh-id',
            type=int,
            help='همگام‌سازی فقط برای یک واردکننده مشخص',
        )

    def handle(self, *args, **options):
        force = options['force']
        varedkonandeh_id = options.get('varedkonandeh_id')

        self.stdout.write(self.style.SUCCESS('شروع همگام‌سازی کیف پول‌ها...'))

        # فیلتر کردن واردکنندگان
        if varedkonandeh_id:
            varedkonandegane = VaredKonandeh.objects.filter(id=varedkonandeh_id)
            if not varedkonandegane.exists():
                self.stdout.write(
                    self.style.ERROR(f'واردکننده با شناسه {varedkonandeh_id} یافت نشد.')
                )
                return
        else:
            varedkonandegane = VaredKonandeh.objects.all()

        total_wallets = 0
        total_entries = 0
        
        with transaction.atomic():
            for varedkonandeh in varedkonandegane:
                self.stdout.write(f'پردازش واردکننده: {varedkonandeh.name}')
                
                # ایجاد یا دریافت کیف پول
                wallet, wallet_created = Wallet.objects.get_or_create(
                    varedkonandeh=varedkonandeh,
                    defaults={
                        'description': f'کیف پول {varedkonandeh.name}',
                        'balance': 0
                    }
                )
                
                if wallet_created:
                    total_wallets += 1
                    self.stdout.write(f'  ✓ کیف پول جدید ایجاد شد')
                elif force:
                    self.stdout.write(f'  → کیف پول موجود پیدا شد')
                else:
                    self.stdout.write(f'  → کیف پول موجود (رد شد)')
                    continue

                # پیدا کردن خریدهای مربوط به این واردکننده
                purchases = Purchase.objects.filter(
                    cargo__vared_konandeh=varedkonandeh,
                    is_canceled=False,
                    is_archived=False
                )
                
                purchase_count = purchases.count()
                self.stdout.write(f'  → {purchase_count} خرید یافت شد')

                # ایجاد ثبت‌های دفتر
                for purchase in purchases:
                    entry = LedgerEntry.create_or_update_entry(purchase)
                    if entry:
                        total_entries += 1

                # محاسبه مجدد موجودی
                wallet.calculate_balance()
                self.stdout.write(
                    f'  ✓ موجودی نهایی: {wallet.balance:,} ریال'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ همگام‌سازی تکمیل شد:\n'
                f'   📊 کیف پول‌های ایجاد شده: {total_wallets}\n'
                f'   📋 ثبت‌های دفتر ایجاد/بروزرسانی شده: {total_entries}\n'
                f'   👥 واردکنندگان پردازش شده: {varedkonandegane.count()}'
            )
        )

        # آمار کلی
        total_balance = Wallet.objects.aggregate(
            total=models.Sum('balance')
        )['total'] or 0
        
        self.stdout.write(
            self.style.WARNING(
                f'\n📈 آمار کلی سیستم:\n'
                f'   💰 کل موجودی سیستم: {total_balance:,} ریال\n'
                f'   🏦 تعداد کل کیف پول‌ها: {Wallet.objects.count()}\n'
                f'   📖 تعداد کل ثبت‌های دفتر: {LedgerEntry.objects.count()}'
            )
        )
        
        # نمایش واردکنندگان با بیشترین بدهی
        top_debtors = Wallet.objects.filter(balance__lt=0).order_by('balance')[:5]
        if top_debtors:
            self.stdout.write(self.style.ERROR('\n🔴 بیشترین بدهی‌ها:'))
            for wallet in top_debtors:
                self.stdout.write(f'   - {wallet.varedkonandeh.name}: {wallet.balance:,} ریال')

        # نمایش واردکنندگان با بیشترین موجودی
        top_creditors = Wallet.objects.filter(balance__gt=0).order_by('-balance')[:5]
        if top_creditors:
            self.stdout.write(self.style.SUCCESS('\n🟢 بیشترین موجودی‌ها:'))
            for wallet in top_creditors:
                self.stdout.write(f'   - {wallet.varedkonandeh.name}: {wallet.balance:,} ریال') 