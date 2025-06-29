from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

# Import BI models
from bi.models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI, UserPreference, DashboardSession
)

# Import core models
from core.CustomerModel import Customer, PhoneNumber, ActivityField, ProductPreference, PaymentPreference
from core.PurchaseModel import Purchase, PurchaseHistory, PurchaseStateChange, PurchaseReceipts
from core.CargoProductModel import CargoProduct, VaredKonandeh, Barbary
from core.SalesAgentModel import SalesAgent

class Command(BaseCommand):
    help = 'حذف انتخابی داده‌های سیستم BI و core'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bi-only',
            action='store_true',
            help='حذف فقط داده‌های BI (داشبورد، چارت، متریک)',
        )
        parser.add_argument(
            '--core-only',
            action='store_true',
            help='حذف فقط داده‌های core (مشتری، خرید، محصول)',
        )
        parser.add_argument(
            '--keep-users',
            action='store_true',
            help='حفظ کاربران و عدم حذف آنها',
        )
        parser.add_argument(
            '--purchases-only',
            action='store_true',
            help='حذف فقط خریدها',
        )
        parser.add_argument(
            '--customers-only',
            action='store_true',
            help='حذف فقط مشتریان',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('⚠️ شروع حذف داده‌ها...'))
        
        if options['bi_only']:
            self.clear_bi_data()
        elif options['core_only']:
            self.clear_core_data()
        elif options['purchases_only']:
            self.clear_purchases_only()
        elif options['customers_only']:
            self.clear_customers_only()
        else:
            # حذف همه چیز
            self.clear_bi_data()
            self.clear_core_data()
            
            if not options['keep_users']:
                self.clear_users()
        
        self.stdout.write(self.style.SUCCESS('✅ حذف داده‌ها با موفقیت انجام شد!'))

    def clear_bi_data(self):
        """حذف داده‌های BI"""
        self.stdout.write('🗑️ حذف داده‌های BI...')
        
        # حذف به ترتیب وابستگی
        deleted_counts = {}
        
        deleted_counts['DashboardSession'] = DashboardSession.objects.all().delete()[0]
        deleted_counts['UserPreference'] = UserPreference.objects.all().delete()[0]
        deleted_counts['Widget'] = Widget.objects.all().delete()[0]
        deleted_counts['Report'] = Report.objects.all().delete()[0]
        deleted_counts['Dashboard'] = Dashboard.objects.all().delete()[0]
        deleted_counts['Chart'] = Chart.objects.all().delete()[0]
        deleted_counts['KPI'] = KPI.objects.all().delete()[0]
        deleted_counts['Filter'] = Filter.objects.all().delete()[0]
        deleted_counts['MetricDefinition'] = MetricDefinition.objects.all().delete()[0]
        deleted_counts['DataSource'] = DataSource.objects.all().delete()[0]
        
        # نمایش آمار حذف
        for model, count in deleted_counts.items():
            if count > 0:
                self.stdout.write(f'  ✓ {count} {model} حذف شد')

    def clear_core_data(self):
        """حذف داده‌های core"""
        self.stdout.write('🗑️ حذف داده‌های core...')
        
        deleted_counts = {}
        
        # حذف به ترتیب وابستگی
        deleted_counts['PurchaseReceipts'] = PurchaseReceipts.objects.all().delete()[0]
        deleted_counts['PurchaseStateChange'] = PurchaseStateChange.objects.all().delete()[0]
        deleted_counts['PurchaseHistory'] = PurchaseHistory.objects.all().delete()[0]
        deleted_counts['Purchase'] = Purchase.objects.all().delete()[0]
        
        deleted_counts['PhoneNumber'] = PhoneNumber.objects.all().delete()[0]
        deleted_counts['Customer'] = Customer.objects.all().delete()[0]
        
        deleted_counts['CargoProduct'] = CargoProduct.objects.all().delete()[0]
        deleted_counts['VaredKonandeh'] = VaredKonandeh.objects.all().delete()[0]
        deleted_counts['Barbary'] = Barbary.objects.all().delete()[0]
        
        # نمایش آمار حذف
        for model, count in deleted_counts.items():
            if count > 0:
                self.stdout.write(f'  ✓ {count} {model} حذف شد')

    def clear_purchases_only(self):
        """حذف فقط خریدها"""
        self.stdout.write('🗑️ حذف فقط خریدها...')
        
        purchase_count = Purchase.objects.count()
        purchase_related_count = PurchaseStateChange.objects.count() + PurchaseHistory.objects.count() + PurchaseReceipts.objects.count()
        
        PurchaseReceipts.objects.all().delete()
        PurchaseStateChange.objects.all().delete()
        PurchaseHistory.objects.all().delete()
        Purchase.objects.all().delete()
        
        self.stdout.write(f'  ✓ {purchase_count} خرید و {purchase_related_count} رکورد مرتبط حذف شد')

    def clear_customers_only(self):
        """حذف فقط مشتریان"""
        self.stdout.write('🗑️ حذف فقط مشتریان...')
        
        # ابتدا خریدهای مرتبط را حذف کنیم
        purchase_count = Purchase.objects.count()
        if purchase_count > 0:
            self.stdout.write(f'  ⚠️ ابتدا {purchase_count} خرید مرتبط حذف می‌شود...')
            self.clear_purchases_only()
        
        customer_count = Customer.objects.count()
        phone_count = PhoneNumber.objects.count()
        
        PhoneNumber.objects.all().delete()
        Customer.objects.all().delete()
        
        self.stdout.write(f'  ✓ {customer_count} مشتری و {phone_count} شماره تلفن حذف شد')

    def clear_users(self):
        """حذف کاربران (جز super user اصلی)"""
        self.stdout.write('🗑️ حذف کاربران...')
        
        # حفظ یک super user برای دسترسی
        main_admin = User.objects.filter(is_superuser=True, username='admin').first()
        
        if main_admin:
            # حذف SalesAgent ها
            SalesAgent.objects.exclude(user=main_admin).delete()
            
            # حذف سایر کاربران
            deleted_users = User.objects.exclude(id=main_admin.id).delete()[0]
            self.stdout.write(f'  ✓ {deleted_users} کاربر حذف شد (admin اصلی حفظ شد)')
        else:
            # اگر admin اصلی نیست، همه رو حذف کن
            SalesAgent.objects.all().delete()
            deleted_users = User.objects.all().delete()[0]
            self.stdout.write(f'  ✓ {deleted_users} کاربر حذف شد')
            self.stdout.write('  ⚠️ تمام کاربران حذف شدند. ممکن است نیاز به ایجاد کاربر جدید داشته باشید.')

    def clear_preference_models(self):
        """حذف مدل‌های preference که ممکن است orphan شده باشند"""
        self.stdout.write('🧹 پاک‌سازی مدل‌های preference...')
        
        # این مدل‌ها معمولاً با customer ها ارتباط دارند
        ActivityField.objects.all().delete()
        ProductPreference.objects.all().delete()
        PaymentPreference.objects.all().delete()
        
        self.stdout.write('  ✓ مدل‌های preference پاک شدند') 