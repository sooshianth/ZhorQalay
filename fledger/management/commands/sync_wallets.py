from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from fledger.models import Wallet, LedgerEntry
from core.PurchaseModel import Purchase
from core.CargoProductModel import VaredKonandeh


class Command(BaseCommand):
    help = 'همگام‌سازی کیف پول‌ها با خریدها و بروزرسانی موجودی‌ها'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-missing-wallets',
            action='store_true',
            help='ایجاد کیف پول‌های ناموجود برای واردکنندگان',
        )
        parser.add_argument(
            '--recalculate-all',
            action='store_true', 
            help='محاسبه مجدد کل موجودی‌ها',
        )
        parser.add_argument(
            '--only-address-sent',
            action='store_true',
            help='فقط خریدهایی که آدرس ارسال شده محاسبه شوند',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('شروع همگام‌سازی کیف پول‌ها...')
        )

        # ایجاد کیف پول‌های ناموجود
        if options['create_missing_wallets']:
            self.create_missing_wallets()

        # همگام‌سازی خریدها با دفتر کل
        self.sync_purchases_to_ledger(options['only_address_sent'])

        # محاسبه مجدد موجودی‌ها
        if options['recalculate_all']:
            self.recalculate_all_wallets()

        self.stdout.write(
            self.style.SUCCESS('همگام‌سازی با موفقیت تکمیل شد.')
        )

    def create_missing_wallets(self):
        """ایجاد کیف پول‌های ناموجود برای واردکنندگان"""
        self.stdout.write('ایجاد کیف پول‌های ناموجود...')
        
        varedkonandehgan = VaredKonandeh.objects.all()
        created_count = 0
        
        for varedkonandeh in varedkonandehgan:
            wallet, created = Wallet.objects.get_or_create(
                varedkonandeh=varedkonandeh,
                defaults={
                    'description': f'کیف پول {varedkonandeh.name}',
                    'balance': 0
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'✅ کیف پول {varedkonandeh.name} ایجاد شد')
        
        self.stdout.write(
            self.style.SUCCESS(f'تعداد {created_count} کیف پول جدید ایجاد شد.')
        )

    def sync_purchases_to_ledger(self, only_address_sent=False):
        """همگام‌سازی خریدها با دفتر کل"""
        self.stdout.write('همگام‌سازی خریدها با دفتر کل...')
        
        # فیلتر خریدها
        purchases = Purchase.objects.filter(
            cargo__isnull=False,
            cargo__vared_konandeh__isnull=False,
            is_canceled=False,
            is_archived=False
        )
        
        if only_address_sent:
            purchases = purchases.filter(is_address_sent='1')
            self.stdout.write('فقط خریدهایی که آدرس ارسال شده محاسبه می‌شوند')
        
        synced_count = 0
        error_count = 0
        
        for purchase in purchases:
            try:
                # بررسی شرایط بر اساس is_address_sent و wallet_index
                if only_address_sent and purchase.is_address_sent != '1':
                    continue
                    
                # تعیین وزن بر اساس wallet_index
                if purchase.wallet_index == '0':
                    weight = purchase.order_weight or 0
                else:  # wallet_index == '1'
                    weight = purchase.delivered_weight or 0
                
                # ایجاد یا بروزرسانی ثبت دفتر
                if weight > 0 and purchase.company_price > 0:
                    entry = LedgerEntry.create_or_update_entry(purchase)
                    if entry:
                        synced_count += 1
                        self.stdout.write(f'✅ خرید {purchase.invoice_id} همگام‌سازی شد')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ خطا در خرید {purchase.invoice_id}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'تعداد {synced_count} خرید همگام‌سازی شد. '
                f'تعداد خطاها: {error_count}'
            )
        )

    def recalculate_all_wallets(self):
        """محاسبه مجدد موجودی تمام کیف پول‌ها"""
        self.stdout.write('محاسبه مجدد موجودی کیف پول‌ها...')
        
        wallets = Wallet.objects.all()
        updated_count = 0
        
        with transaction.atomic():
            for wallet in wallets:
                try:
                    old_balance = wallet.balance
                    new_balance = wallet.calculate_balance()
                    
                    if old_balance != new_balance:
                        updated_count += 1
                        self.stdout.write(
                            f'✅ {wallet.varedkonandeh.name}: '
                            f'{old_balance:,.0f} ← {new_balance:,.0f} ریال'
                        )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ خطا در محاسبه {wallet.varedkonandeh.name}: {str(e)}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'تعداد {updated_count} کیف پول بروزرسانی شد.')
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