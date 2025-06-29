from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

# Import BI models
from bi.models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI
)

# Import core models
from core.CustomerModel import Customer, PhoneNumber
from core.PurchaseModel import Purchase
from core.CargoProductModel import CargoProduct

class Command(BaseCommand):
    help = 'پاک کردن داده‌های جعلی ایجاد شده توسط کامند complete_bi_setup'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧹 شروع پاک کردن داده‌های جعلی...'))
        
        # آمار قبل از حذف
        initial_customers = Customer.objects.count()
        initial_purchases = Purchase.objects.count()
        
        self.stdout.write(f'📊 وضعیت قبل از پاکسازی:')
        self.stdout.write(f'  • مشتریان: {initial_customers:,}')
        self.stdout.write(f'  • خریدها: {initial_purchases:,}')
        
        # شناسایی و حذف خریدهای جعلی (آخرین 400 خرید)
        self.stdout.write('\n🎯 حذف خریدهای جعلی...')
        fake_purchases = Purchase.objects.order_by('-created_at')[:400]
        fake_purchase_ids = [p.id for p in fake_purchases]
        
        if fake_purchase_ids:
            deleted_purchases, _ = Purchase.objects.filter(id__in=fake_purchase_ids).delete()
            self.stdout.write(f'  ✓ {deleted_purchases} خرید جعلی حذف شد')
        else:
            self.stdout.write('  ⚠️ خریدی برای حذف یافت نشد')
        
        # شناسایی و حذف مشتریان جعلی (آخرین 150 مشتری)
        self.stdout.write('\n👥 حذف مشتریان جعلی...')
        fake_customers = Customer.objects.order_by('-created_at')[:150]
        fake_customer_ids = [c.id for c in fake_customers]
        
        if fake_customer_ids:
            deleted_customers, _ = Customer.objects.filter(id__in=fake_customer_ids).delete()
            self.stdout.write(f'  ✓ {deleted_customers} مشتری جعلی حذف شد')
        else:
            self.stdout.write('  ⚠️ مشتری‌ای برای حذف یافت نشد')
        
        # حذف داده‌های BI
        self.stdout.write('\n🔧 حذف داده‌های BI...')
        Widget.objects.all().delete()
        Chart.objects.all().delete()
        Dashboard.objects.all().delete()
        KPI.objects.all().delete()
        Filter.objects.all().delete()
        MetricDefinition.objects.all().delete()
        DataSource.objects.all().delete()
        self.stdout.write('  ✓ تمام داده‌های BI حذف شد')
        
        # آمار نهایی
        final_customers = Customer.objects.count()
        final_purchases = Purchase.objects.count()
        
        self.stdout.write(f'\n📈 نتیجه نهایی:')
        self.stdout.write(f'  • مشتریان باقی‌مانده: {final_customers:,}')
        self.stdout.write(f'  • خریدهای باقی‌مانده: {final_purchases:,}')
        
        customers_removed = initial_customers - final_customers
        purchases_removed = initial_purchases - final_purchases
        
        self.stdout.write(f'\n🎉 خلاصه:')
        self.stdout.write(f'  • {customers_removed:,} مشتری جعلی حذف شد')
        self.stdout.write(f'  • {purchases_removed:,} خرید جعلی حذف شد')
        self.stdout.write(f'  • داده‌های BI پاک شد')
        
        self.stdout.write(self.style.SUCCESS('\n✅ پاکسازی با موفقیت کامل شد!'))
        self.stdout.write('💡 حالا می‌توانید با --use-existing-data دوباره setup کنید') 