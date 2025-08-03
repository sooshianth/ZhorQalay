from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, datetime
import random
from django.apps import apps
import uuid

# Import BI models
from bi.models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI
)

# Import core models
from core.CustomerModel import Customer, PhoneNumber, ActivityField, ProductPreference, PaymentPreference
from core.PurchaseModel import Purchase
from core.CargoProductModel import CargoProduct, VaredKonandeh, Barbary
from core.SalesAgentModel import SalesAgent

class Command(BaseCommand):
    help = 'راه‌اندازی کامل سیستم BI - ایجاد داده‌های واقعی + منابع داده + چارت‌ها'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-bi-only',
            action='store_true',
            help='حذف فقط داده‌های BI (نگه داشتن داده‌های اصلی سیستم)',
        )
        parser.add_argument(
            '--clear-all',
            action='store_true',
            help='حذف تمام داده‌های قبلی (BI + داده‌های اصلی)',
        )
        parser.add_argument(
            '--use-existing-data',
            action='store_true',
            help='استفاده از داده‌های موجود در سیستم بجای ایجاد داده‌های جدید',
        )
        parser.add_argument(
            '--customers',
            type=int,
            default=150,
            help='تعداد مشتریان برای ایجاد (فقط در صورت عدم استفاده از داده‌های موجود)',
        )
        parser.add_argument(
            '--purchases',
            type=int,
            default=400,
            help='تعداد خریدها برای ایجاد (فقط در صورت عدم استفاده از داده‌های موجود)',
        )
        parser.add_argument(
            '--skip-data',
            action='store_true',
            help='رد کردن ایجاد داده‌های واقعی و فقط BI setup',
        )
        parser.add_argument(
            '--clean-fake-data',
            action='store_true',
            help='پاک کردن داده‌های جعلی ایجاد شده توسط کامند',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 شروع راه‌اندازی کامل سیستم BI...'))
        
        if options['clear_all']:
            self.clear_all_data()
        elif options['clear_bi_only']:
            self.clear_bi_data_only()
        elif options['clean_fake_data']:
            self.clean_fake_data()
            return
        
        # بررسی داده‌های موجود در سیستم
        existing_customers = Customer.objects.count()
        existing_purchases = Purchase.objects.count()
        existing_products = CargoProduct.objects.count()
        
        self.stdout.write(f'📊 آمار داده‌های موجود:')
        self.stdout.write(f'  • مشتریان: {existing_customers:,}')
        self.stdout.write(f'  • خریدها: {existing_purchases:,}')  
        self.stdout.write(f'  • محصولات: {existing_products:,}')
        
        # مرحله 1: آماده‌سازی داده‌ها
        if not options['skip_data']:
            if options['use_existing_data']:
                # استفاده از داده‌های موجود
                if existing_customers > 0 and existing_purchases > 0:
                    self.stdout.write(self.style.SUCCESS('\n✨ استفاده از داده‌های موجود در سیستم'))
                    self.stdout.write(f'  ✓ {existing_customers:,} مشتری موجود')
                    self.stdout.write(f'  ✓ {existing_purchases:,} خرید موجود')
                    self.stdout.write(f'  ✓ {existing_products:,} محصول موجود')
                    
                    # فقط اگر کاربر یا کارشناس فروش نداشته باشیم، بسازیم
                    if User.objects.count() == 0:
                        self.stdout.write('  👥 ایجاد کاربران پایه...')
                        self.create_users()
                    
                    if SalesAgent.objects.count() == 0:
                        self.stdout.write('  👔 ایجاد کارشناسان فروش پایه...')
                        self.create_users()  # این شامل ایجاد sales agents هم هست
                        
                    # فقط اگر محصول نداشته باشیم
                    if existing_products == 0:
                        self.stdout.write('  📦 ایجاد محصولات پایه...')
                        self.create_real_products()
                        
                    self.stdout.write('  🎉 آماده! از داده‌های موجود استفاده می‌کنیم')
                else:
                    self.stdout.write(self.style.WARNING('\n⚠️ داده‌های کافی موجود نیست!'))
                    self.stdout.write(f'  • مشتریان موجود: {existing_customers:,}')
                    self.stdout.write(f'  • خریدهای موجود: {existing_purchases:,}')
                    self.stdout.write('  💡 لطفاً ابتدا داده‌های واقعی وارد کنید یا گزینه --use-existing-data را حذف کنید')
                    return
            else:
                # تشخیص خودکار - اگر داده موجود باشه، از اون استفاده کن
                if existing_customers > 5 and existing_purchases > 10:
                    self.stdout.write(self.style.SUCCESS(f'\n🔍 تشخیص خودکار: {existing_purchases:,} خرید و {existing_customers:,} مشتری موجود!'))
                    self.stdout.write('  ✨ از داده‌های موجود استفاده می‌کنم...')
                    
                    # فقط اگر کاربر یا کارشناس فروش نداشته باشیم
                    if User.objects.count() == 0:
                        self.create_users()
                    if SalesAgent.objects.count() == 0:
                        self.create_users()
                    if existing_products == 0:
                        self.create_real_products()
                else:
                    self.stdout.write(self.style.SUCCESS('\n📊 مرحله 1: ایجاد داده‌های نمونه'))
                    self.stdout.write(f'⚠️ داده‌های کم موجود: {existing_customers} مشتری، {existing_purchases} خرید')
                    self.create_base_data(options['customers'], options['purchases'])
        
        # مرحله 2: راه‌اندازی سیستم BI
        self.stdout.write(self.style.SUCCESS('\n🔧 مرحله 2: راه‌اندازی سیستم BI'))
        self.setup_bi_system()
        
        # نمایش آمار نهایی
        final_customers = Customer.objects.count()
        final_purchases = Purchase.objects.count()
        final_products = CargoProduct.objects.count()
        final_users = User.objects.count()
        final_sales_agents = SalesAgent.objects.count()
        
        # نمایش تغییرات
        customers_change = final_customers - existing_customers
        purchases_change = final_purchases - existing_purchases
        products_change = final_products - existing_products
        
        self.stdout.write(self.style.SUCCESS('\n✅ راه‌اندازی کامل سیستم BI با موفقیت انجام شد!'))
        self.stdout.write(f'📈 آمار نهایی سیستم:')
        self.stdout.write(f'  • مشتریان: {final_customers:,} {"(+" + str(customers_change) + " جدید)" if customers_change > 0 else "(بدون تغییر)"}')
        self.stdout.write(f'  • خریدها: {final_purchases:,} {"(+" + str(purchases_change) + " جدید)" if purchases_change > 0 else "(بدون تغییر)"}')
        self.stdout.write(f'  • محصولات: {final_products:,} {"(+" + str(products_change) + " جدید)" if products_change > 0 else "(بدون تغییر)"}')
        self.stdout.write(f'  • کاربران: {final_users:,}')
        self.stdout.write(f'  • کارشناسان فروش: {final_sales_agents:,}')
        
        if options['use_existing_data']:
            self.stdout.write(self.style.SUCCESS(f'\n🎉 عالی! از {final_purchases:,} خرید واقعی موجود در سیستم استفاده شد'))
        elif final_purchases > 1000:
            self.stdout.write(self.style.SUCCESS(f'\n🔍 توجه: سیستم {final_purchases:,} خرید موجود تشخیص داد و از آن‌ها استفاده کرد'))
            
        self.stdout.write('\n🌐 برای مشاهده داشبورد به آدرس /bi/dashboard/ بروید')

    def clean_fake_data(self):
        """پاک کردن داده‌های جعلی ایجاد شده"""
        self.stdout.write('🧹 پاک کردن داده‌های جعلی...')
        
        # شناسایی و حذف خریدهای جعلی (آخرین 400 خرید که احتمالاً جعلی هستند)
        fake_purchases = Purchase.objects.order_by('-created_at')[:400]
        fake_purchase_ids = [p.id for p in fake_purchases]
        deleted_purchases = Purchase.objects.filter(id__in=fake_purchase_ids).delete()[0]
        
        # شناسایی و حذف مشتریان جعلی (آخرین 150 مشتری)
        fake_customers = Customer.objects.order_by('-created_at')[:150]
        fake_customer_ids = [c.id for c in fake_customers]
        deleted_customers = Customer.objects.filter(id__in=fake_customer_ids).delete()[0]
        
        # حذف داده‌های BI هم
        Widget.objects.all().delete()
        Chart.objects.all().delete()
        Dashboard.objects.all().delete()
        KPI.objects.all().delete()
        Filter.objects.all().delete()
        MetricDefinition.objects.all().delete()
        DataSource.objects.all().delete()
        
        self.stdout.write(f'  ✓ {deleted_purchases} خرید جعلی حذف شد')
        self.stdout.write(f'  ✓ {deleted_customers} مشتری جعلی حذف شد')
        self.stdout.write('  ✓ داده‌های BI پاک شد')
        
        # نمایش آمار باقی‌مانده
        remaining_customers = Customer.objects.count()
        remaining_purchases = Purchase.objects.count()
        self.stdout.write(f'📊 داده‌های باقی‌مانده:')
        self.stdout.write(f'  • مشتریان: {remaining_customers:,}')
        self.stdout.write(f'  • خریدها: {remaining_purchases:,}')

    def clear_bi_data_only(self):
        """حذف فقط داده‌های BI"""
        self.stdout.write('🗑️ حذف داده‌های BI...')
        
        # حذف داده‌های BI
        Widget.objects.all().delete()
        Chart.objects.all().delete()
        Dashboard.objects.all().delete()
        KPI.objects.all().delete()
        Filter.objects.all().delete()
        MetricDefinition.objects.all().delete()
        DataSource.objects.all().delete()
        
        self.stdout.write('  ✓ داده‌های BI حذف شدند (داده‌های اصلی حفظ شدند)')

    def clear_all_data(self):
        """حذف تمام داده‌های قبلی"""
        self.stdout.write('🗑️ حذف تمام داده‌های قبلی...')
        
        # حذف داده‌های BI
        Widget.objects.all().delete()
        Chart.objects.all().delete()
        Dashboard.objects.all().delete()
        KPI.objects.all().delete()
        Filter.objects.all().delete()
        MetricDefinition.objects.all().delete()
        DataSource.objects.all().delete()
        
        # حذف داده‌های اصلی
        Purchase.objects.all().delete()
        Customer.objects.all().delete()
        CargoProduct.objects.all().delete()
        VaredKonandeh.objects.all().delete()
        Barbary.objects.all().delete()
        
        self.stdout.write('  ✓ تمام داده‌های قبلی حذف شدند')

    def create_base_data(self, customer_count, purchase_count):
        """ایجاد داده‌های پایه"""
        # ایجاد کاربران
        self.create_users()
        
        # ایجاد واردکنندگان و باربری‌ها
        self.create_vendors_and_transporters()
        
        # ایجاد محصولات
        self.create_real_products()
        
        # ایجاد مشتریان
        self.create_real_customers(customer_count)
        
        # ایجاد خریدها
        self.create_real_purchases(purchase_count)

    def create_users(self):
        """ایجاد کاربران مورد نیاز"""
        self.stdout.write('👥 ایجاد کاربران...')
        
        # Admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@simurgh360.com',
                'first_name': 'مدیر',
                'last_name': 'سیستم',
                'is_superuser': True,
                'is_staff': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write('  ✓ کاربر مدیر ایجاد شد')

        # Sales agents
        sales_agents_data = [
            {'username': 'sales_manager', 'first_name': 'احمد', 'last_name': 'کریمی', 'factor_code': '10'},
            {'username': 'sales_agent_1', 'first_name': 'فاطمه', 'last_name': 'احمدی', 'factor_code': '11'},
            {'username': 'sales_agent_2', 'first_name': 'محمد', 'last_name': 'رضایی', 'factor_code': '12'},
            {'username': 'sales_agent_3', 'first_name': 'زهرا', 'last_name': 'محمدی', 'factor_code': '13'},
        ]
        
        for agent_data in sales_agents_data:
            user, created = User.objects.get_or_create(
                username=agent_data['username'],
                defaults={
                    'first_name': agent_data['first_name'],
                    'last_name': agent_data['last_name'],
                    'email': f"{agent_data['username']}@simurgh360.com"
                }
            )
            if created:
                user.set_password('123456')
                user.save()
                
            # ایجاد SalesAgent
            SalesAgent.objects.get_or_create(
                user=user,
                defaults={
                    'name': f"{agent_data['first_name']} {agent_data['last_name']}",
                    'phone_number': f'091{random.randint(10000000, 99999999)}',
                    'factor_code': agent_data['factor_code']
                }
            )
            if created:
                self.stdout.write(f'  ✓ کارشناس فروش {agent_data["first_name"]} {agent_data["last_name"]} ایجاد شد')

    def create_vendors_and_transporters(self):
        """ایجاد واردکنندگان و باربری‌ها"""
        self.stdout.write('🚛 ایجاد واردکنندگان و باربری‌ها...')
        
        # واردکنندگان
        vendors_data = [
            {'name': 'شرکت پارس غلات', 'phone': '02133445566', 'balance': 5000000000},
            {'name': 'شرکت نهادینه آسیا', 'phone': '02122334455', 'balance': 3000000000},
            {'name': 'شرکت کشاورزی البرز', 'phone': '02644556677', 'balance': 4000000000},
            {'name': 'شرکت تجارت کاسپین', 'phone': '01122334455', 'balance': 2500000000},
            {'name': 'شرکت غلات خاورمیانه', 'phone': '07633445566', 'balance': 3500000000},
        ]
        
        for vendor_data in vendors_data:
            VaredKonandeh.objects.get_or_create(
                name=vendor_data['name'],
                defaults={
                    'phone_number': vendor_data['phone'],
                    'balance': vendor_data['balance'],
                    'email': f"info@{vendor_data['name'].replace(' ', '').lower()}.com",
                    'website': f"www.{vendor_data['name'].replace(' ', '').lower()}.com"
                }
            )
        
        # باربری‌ها
        transporters_data = [
            {'name': 'باربری اطلس', 'phone': '09121234567'},
            {'name': 'باربری پارس', 'phone': '09122345678'},
            {'name': 'باربری سپهر', 'phone': '09123456789'},
            {'name': 'باربری فردوس', 'phone': '09124567890'},
            {'name': 'باربری آریا', 'phone': '09125678901'},
        ]
        
        for trans_data in transporters_data:
            Barbary.objects.get_or_create(
                name=trans_data['name'],
                defaults={
                    'phone_number': trans_data['phone'],
                    'description': f'باربری {trans_data["name"]}',
                    'email': f"info@{trans_data['name'].replace(' ', '').lower()}.com"
                }
            )

    def create_real_products(self):
        """ایجاد محصولات واقعی"""
        self.stdout.write('🌾 ایجاد محصولات واقعی...')
        
        vendors = list(VaredKonandeh.objects.all())
        barbaries = list(Barbary.objects.all())
        
        products_data = [
            # کنجاله سویا
            {'type': 'bazaargah', 'cottage': '12345001', 'product': 'soy_meal', 'country': 'argentina', 
             'company_price': 175000, 'customer_price': 185000, 'weight': 25000000, 'port': 'امام خمینی'},
            {'type': 'bazaargah', 'cottage': '12345002', 'product': 'soy_meal', 'country': 'brazil', 
             'company_price': 172000, 'customer_price': 182000, 'weight': 30000000, 'port': 'امام خمینی'},
            
            # ذرت
            {'type': 'bazaargah', 'cottage': '12345003', 'product': 'corn', 'country': 'ukraine', 
             'company_price': 155000, 'customer_price': 165000, 'weight': 40000000, 'port': 'امام خمینی'},
            {'type': 'bazaargah', 'cottage': '12345004', 'product': 'corn', 'country': 'brazil', 
             'company_price': 152000, 'customer_price': 162000, 'weight': 35000000, 'port': 'امام خمینی'},
            
            # جو
            {'type': 'bazaargah', 'cottage': '12345005', 'product': 'barley', 'country': 'russia', 
             'company_price': 135000, 'customer_price': 145000, 'weight': 30000000, 'port': 'انزلی'},
            {'type': 'bazaargah', 'cottage': '12345006', 'product': 'barley', 'country': 'kazakhstan', 
             'company_price': 132000, 'customer_price': 142000, 'weight': 28000000, 'port': 'انزلی'},
            
            # محصولات غیربازارگاه
            {'type': 'non_bazaargah', 'cottage': '901', 'product': 'soy_meal', 'country': 'iran', 
             'company_price': 190000, 'customer_price': 200000, 'weight': 15000000, 'port': 'سایر'},
            {'type': 'non_bazaargah', 'cottage': '902', 'product': 'corn', 'country': 'iran', 
             'company_price': 170000, 'customer_price': 180000, 'weight': 12000000, 'port': 'سایر'},
        ]
        
        for product_data in products_data:
            vendor = random.choice(vendors) if vendors else None
            barbary = random.choice(barbaries) if barbaries else None
            
            CargoProduct.objects.get_or_create(
                cottage=product_data['cottage'],
                defaults={
                    'type': product_data['type'],
                    'product_type': product_data['product'],
                    'country': product_data['country'],
                    'company_price': product_data['company_price'],
                    'customer_price': product_data['customer_price'],
                    'weight': product_data['weight'],
                    'port': product_data['port'],
                    'vared_konandeh': vendor,
                    'barbary': barbary,
                    'loading_time': f'هفته {random.randint(1, 4)} {random.choice(["فروردین", "اردیبهشت", "خرداد"])} ۱۴۰۳',
                    'description': f'محصول درجه یک از {dict(CargoProduct.COUNTRIES)[product_data["country"]]}',
                    'status': True
                }
            )

    def create_real_customers(self, count):
        """ایجاد مشتریان واقعی"""
        self.stdout.write(f'👥 ایجاد {count} مشتری واقعی...')
        
        first_names = [
            'احمد', 'محمد', 'علی', 'حسن', 'حسین', 'مهدی', 'رضا', 'کریم',
            'فاطمه', 'زهرا', 'مریم', 'فهیمه', 'سکینه', 'زینب', 'طاهره', 'معصومه',
            'عباس', 'جعفر', 'موسی', 'یوسف', 'داود', 'سلیمان', 'ابراهیم', 'اسماعیل'
        ]
        
        last_names = [
            'احمدی', 'محمدی', 'علوی', 'حسینی', 'موسوی', 'رضایی', 'کریمی', 'نوری',
            'صادقی', 'باقری', 'جعفری', 'طاهری', 'شریفی', 'فرهادی', 'کاظمی', 'مرادی',
            'اسدی', 'قاسمی', 'یوسفی', 'ابراهیمی', 'داودی', 'سلیمانی', 'اسماعیلی', 'حیدری'
        ]
        
        cities = [
            'تهران', 'مشهد', 'اصفهان', 'کرج', 'شیراز', 'تبریز', 'قم', 'اهواز',
            'کرمانشاه', 'ارومیه', 'رشت', 'زاهدان', 'کرمان', 'همدان', 'یزد', 'اردبیل',
            'بندرعباس', 'آبادان', 'زنجان', 'سنندج', 'قزوین', 'خرم‌آباد', 'گرگان', 'ساری'
        ]
        
        sales_agents = list(SalesAgent.objects.all())
        
        # ایجاد preference objects
        activity_fields = []
        for code, display in [('chicken', 'مرغدار'), ('livestock', 'دامدار'), ('factory', 'کارخانه خوراک')]:
            field, created = ActivityField.objects.get_or_create(code=code)
            activity_fields.append(field)
        
        payment_prefs = []
        for code, display in [('cash', 'نقدی'), ('bazaargah', 'بازارگاه')]:
            pref, created = PaymentPreference.objects.get_or_create(code=code)
            payment_prefs.append(pref)
        
        product_prefs = []
        for code, display in [('soy_meal', 'کنجاله سویا'), ('corn', 'ذرت'), ('barley', 'جو')]:
            pref, created = ProductPreference.objects.get_or_create(code=code)
            product_prefs.append(pref)
        
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            full_name = f'{first_name} {last_name}'
            phone_number = f'9{random.randint(100000000, 999999999)}'
            
            customer = Customer.objects.create(
                name=full_name,
                city=random.choice(cities),
                phone_number=phone_number,
                whatsapp_preference=random.choice([True, False]),
                sms_preference=random.choice([True, True, True, False]),
                is_bazaargah_enjoyer=random.choice([True, True, False]),
                is_favorite=random.choice([True, False, False, False]),
                is_active=True,
                quota=f'{random.randint(5, 50)} تن در ماه'
            )
            
            # اضافه کردن شماره تلفن اصلی
            PhoneNumber.objects.create(
                customer=customer,
                number=phone_number,
                is_primary=True,
                sms_enabled=customer.sms_preference,
                description='شماره اصلی'
            )
            
            # تخصیص کارشناس فروش
            if sales_agents:
                assigned_agents = random.sample(sales_agents, random.randint(1, min(2, len(sales_agents))))
                customer.sales_agent.set(assigned_agents)
            
            # اضافه کردن preferences
            customer.field_of_activity.set(random.sample(activity_fields, random.randint(1, 2)))
            customer.purchase_preferences.set(random.sample(payment_prefs, random.randint(1, 2)))
            customer.product_preferences.set(random.sample(product_prefs, random.randint(1, 3)))

    def create_real_purchases(self, count):
        """ایجاد خریدهای واقعی"""
        self.stdout.write(f'💰 ایجاد {count} خرید واقعی...')
        
        customers = list(Customer.objects.all())
        products = list(CargoProduct.objects.all())
        sales_agents = list(SalesAgent.objects.all())
        
        if not customers or not products:
            self.stdout.write(self.style.ERROR('ابتدا مشتریان و محصولات را ایجاد کنید'))
            return
        
        states = [
            'PAYMENT_VERIFIED', 'ALLOCATION_APPROVED', 'ADDRESS_SENT',
            'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 'PURCHASE_CLOSED',
            'FULLY_SETTLED', 'INVOICE_ISSUED'
        ]
        
        addresses = [
            'تهران، خیابان ولیعصر، کوچه شهید احمدی، پلاک ۱۲۳',
            'مشهد، بلوار وکیل‌آباد، خیابان امام رضا، پلاک ۴۵۶',
            'اصفهان، خیابان چهارباغ، کوچه گلستان، پلاک ۷۸۹',
            'شیراز، خیابان زند، کوچه حافظ، پلاک ۱۰۱'
        ]
        
        for i in range(count):
            customer = random.choice(customers)
            product = random.choice(products)
            
            order_weight = random.randint(10000, 100000)
            amount_paid = order_weight * product.customer_price
            
            purchase_number = None
            if product.type_of_product == 'bazaargah':
                purchase_number = str(random.randint(1000000, 9999999))
            
            days_ago = random.randint(1, 180)
            purchase_date = timezone.now() - timedelta(days=days_ago)
            
            purchase = Purchase.objects.create(
                customer=customer,
                cargo=product,
                state=random.choice(states),
                type=product.type_of_product,
                order_weight=order_weight,
                delivered_weight=order_weight - random.randint(0, 1000),
                amount_paid=amount_paid,
                company_price=product.company_price,
                customer_price=product.customer_price,
                payment_method=random.choice(['نقدی', 'توافقی']),
                purchase_number=purchase_number,
                tracking_number=str(random.randint(100000, 999999)) if purchase_number else None,
                address=random.choice(addresses),
                priority=random.choice(['low', 'medium', 'high']),
                created_at=purchase_date,
                updated_at=purchase_date + timedelta(hours=random.randint(1, 24))
            )
            
            if sales_agents:
                assigned_agent = random.choice(sales_agents)
                purchase.unique_sales_agent = assigned_agent
                purchase.unique_sales_agent_code = assigned_agent.factor_code
                purchase.save()

    def setup_bi_system(self):
        """راه‌اندازی سیستم BI"""
        # ایجاد منابع داده
        self.create_data_sources()
        
        # ایجاد متریک‌ها
        self.create_metrics()
        
        # ایجاد فیلترها
        self.create_filters()
        
        # ایجاد چارت‌ها
        self.create_charts()
        
        # ایجاد KPI ها
        self.create_kpis()
        
        # ایجاد داشبورد
        self.create_dashboard()

    def create_data_sources(self):
        """ایجاد منابع داده"""
        self.stdout.write('📊 ایجاد منابع داده...')
        
        data_sources = [
            {
                'name': 'مشتریان',
                'app_name': 'core',
                'model_name': 'Customer',
                'description': 'اطلاعات کامل مشتریان شامل داده‌های تماس و ترجیحات'
            },
            {
                'name': 'خریدها',
                'app_name': 'core', 
                'model_name': 'Purchase',
                'description': 'تمام خریدهای انجام شده توسط مشتریان'
            },
            {
                'name': 'محصولات',
                'app_name': 'core',
                'model_name': 'CargoProduct',
                'description': 'کوتاژها و محصولات موجود'
            },
            {
                'name': 'کارشناسان فروش',
                'app_name': 'core',
                'model_name': 'SalesAgent',
                'description': 'اطلاعات کارشناسان فروش'
            }
        ]
        
        for ds_data in data_sources:
            data_source, created = DataSource.objects.get_or_create(
                name=ds_data['name'],
                defaults={
                    'type': 'model',
                    'app_name': ds_data['app_name'],
                    'model_name': ds_data['model_name'],
                    'description': ds_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  ✓ منبع داده "{ds_data["name"]}" ایجاد شد')

    def create_metrics(self):
        """ایجاد متریک‌های اصلی"""
        self.stdout.write('📈 ایجاد متریک‌ها...')
        
        customer_ds = DataSource.objects.get(name='مشتریان')
        purchase_ds = DataSource.objects.get(name='خریدها')
        product_ds = DataSource.objects.get(name='محصولات')
        
        metrics = [
            # متریک‌های مشتری
            {
                'name': 'total_customers',
                'display_name': 'تعداد کل مشتریان',
                'data_source': customer_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل مشتریان ثبت شده در سیستم'
            },
            {
                'name': 'active_customers',
                'display_name': 'مشتریان فعال',
                'data_source': customer_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'filter_expression': '{"is_active": True}',
                'description': 'تعداد مشتریان فعال'
            },
            
            # متریک‌های خرید
            {
                'name': 'total_purchases',
                'display_name': 'تعداد کل خریدها',
                'data_source': purchase_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل خریدهای انجام شده'
            },
            {
                'name': 'total_sales_amount',
                'display_name': 'مجموع فروش',
                'data_source': purchase_ds,
                'field_name': 'amount_paid',
                'aggregation_type': 'sum',
                'unit': 'ریال',
                'description': 'مجموع مبلغ فروش‌های انجام شده'
            },
            {
                'name': 'average_order_value',
                'display_name': 'میانگین ارزش سفارش',
                'data_source': purchase_ds,
                'field_name': 'amount_paid',
                'aggregation_type': 'avg',
                'unit': 'ریال',
                'description': 'میانگین ارزش هر سفارش'
            },
            {
                'name': 'total_weight_sold',
                'display_name': 'کل وزن فروخته شده',
                'data_source': purchase_ds,
                'field_name': 'order_weight',
                'aggregation_type': 'sum',
                'unit': 'کیلوگرم',
                'description': 'مجموع وزن محصولات فروخته شده'
            },
            
            # متریک‌های محصول
            {
                'name': 'total_products',
                'display_name': 'تعداد کل محصولات',
                'data_source': product_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل کوتاژهای موجود'
            },
            {
                'name': 'available_inventory',
                'display_name': 'موجودی قابل فروش',
                'data_source': product_ds,
                'field_name': 'weight',
                'aggregation_type': 'sum',
                'unit': 'کیلوگرم',
                'filter_expression': '{"status": True}',
                'description': 'مجموع وزن محصولات قابل فروش'
            }
        ]
        
        for metric_data in metrics:
            metric, created = MetricDefinition.objects.get_or_create(
                name=metric_data['name'],
                defaults=metric_data
            )
            if created:
                self.stdout.write(f'  ✓ متریک "{metric_data["display_name"]}" ایجاد شد')

    def create_filters(self):
        """ایجاد فیلترهای اصلی"""
        self.stdout.write('🔍 ایجاد فیلترها...')
        
        customer_ds = DataSource.objects.get(name='مشتریان')
        purchase_ds = DataSource.objects.get(name='خریدها')
        product_ds = DataSource.objects.get(name='محصولات')
        
        filters = [
            {
                'name': 'city_filter',
                'display_name': 'شهر',
                'data_source': customer_ds,
                'field_name': 'city',
                'filter_type': 'select',
                'default_operator': 'eq'
            },
            {
                'name': 'purchase_state_filter',
                'display_name': 'وضعیت خرید',
                'data_source': purchase_ds,
                'field_name': 'state',
                'filter_type': 'select',
                'default_operator': 'eq'
            },
            {
                'name': 'product_type_filter',
                'display_name': 'نوع محصول',
                'data_source': product_ds,
                'field_name': 'product_type',
                'filter_type': 'select',
                'default_operator': 'eq'
            },
            {
                'name': 'date_range_filter',
                'display_name': 'بازه زمانی',
                'data_source': purchase_ds,
                'field_name': 'created_at',
                'filter_type': 'date_range',
                'default_operator': 'between'
            }
        ]
        
        for filter_data in filters:
            filter_obj, created = Filter.objects.get_or_create(
                name=filter_data['name'],
                defaults=filter_data
            )
            if created:
                self.stdout.write(f'  ✓ فیلتر "{filter_data["display_name"]}" ایجاد شد')

    def create_charts(self):
        """ایجاد نمودارهای اصلی"""
        self.stdout.write('📊 ایجاد نمودارها...')
        
        purchase_ds = DataSource.objects.get(name='خریدها')
        customer_ds = DataSource.objects.get(name='مشتریان')
        product_ds = DataSource.objects.get(name='محصولات')
        
        # دریافت متریک‌ها
        total_sales = MetricDefinition.objects.get(name='total_sales_amount')
        total_purchases = MetricDefinition.objects.get(name='total_purchases')
        total_weight = MetricDefinition.objects.get(name='total_weight_sold')
        total_customers = MetricDefinition.objects.get(name='total_customers')
        
        charts = [
            {
                'name': 'فروش ماهانه',
                'chart_type': 'purchase_timeline',
                'data_source': purchase_ds,
                'x_axis_field': 'created_at',
                'time_period': 'month',
                'metrics': [total_sales, total_purchases]
            },
            {
                'name': 'توزیع محصولات',
                'chart_type': 'pie',
                'data_source': purchase_ds,
                'x_axis_field': 'cargo__product_type',
                'group_by_field': 'cargo__product_type',
                'metrics': [total_weight]
            },
            {
                'name': 'وضعیت خریدها',
                'chart_type': 'doughnut',
                'data_source': purchase_ds,
                'x_axis_field': 'state',
                'group_by_field': 'state',
                'metrics': [total_purchases]
            },
            {
                'name': 'رشد مشتریان',
                'chart_type': 'customer_activity',
                'data_source': customer_ds,
                'x_axis_field': 'created_at',
                'time_period': 'month',
                'metrics': [total_customers]
            },
            {
                'name': 'عملکرد محصولات',
                'chart_type': 'product_performance',
                'data_source': purchase_ds,
                'x_axis_field': 'cargo__product_type',
                'group_by_field': 'cargo__product_type',
                'metrics': [total_weight, total_sales]
            },
            {
                'name': 'نقشه فروش ایران',
                'chart_type': 'map_iran',
                'data_source': customer_ds,
                'x_axis_field': 'city',
                'group_by_field': 'city',
                'metrics': [total_customers]
            }
        ]
        
        for chart_data in charts:
            metrics = chart_data.pop('metrics')
            chart, created = Chart.objects.get_or_create(
                name=chart_data['name'],
                defaults=chart_data
            )
            if created:
                chart.y_axis_metrics.set(metrics)
                self.stdout.write(f'  ✓ نمودار "{chart_data["name"]}" ایجاد شد')

    def create_kpis(self):
        """ایجاد KPI های اصلی"""
        self.stdout.write('🎯 ایجاد KPI ها...')
        
        total_sales = MetricDefinition.objects.get(name='total_sales_amount')
        total_customers = MetricDefinition.objects.get(name='total_customers')
        avg_order = MetricDefinition.objects.get(name='average_order_value')
        total_purchases = MetricDefinition.objects.get(name='total_purchases')
        
        kpis = [
            {
                'name': 'monthly_sales_kpi',
                'display_name': 'فروش ماهانه',
                'metric': total_sales,
                'kpi_type': 'currency',
                'target_value': 1000000000,
                'warning_threshold': 800000000,
                'critical_threshold': 500000000,
                'comparison_period': 'month'
            },
            {
                'name': 'customer_growth_kpi',
                'display_name': 'رشد مشتریان',
                'metric': total_customers,
                'kpi_type': 'number',
                'target_value': 200,
                'warning_threshold': 150,
                'critical_threshold': 100,
                'comparison_period': 'month'
            },
            {
                'name': 'average_order_kpi',
                'display_name': 'میانگین ارزش سفارش',
                'metric': avg_order,
                'kpi_type': 'currency',
                'target_value': 50000000,
                'warning_threshold': 30000000,
                'critical_threshold': 20000000,
                'comparison_period': 'week'
            },
            {
                'name': 'total_orders_kpi',
                'display_name': 'کل سفارشات',
                'metric': total_purchases,
                'kpi_type': 'number',
                'target_value': 500,
                'warning_threshold': 300,
                'critical_threshold': 200,
                'comparison_period': 'month'
            }
        ]
        
        for kpi_data in kpis:
            kpi, created = KPI.objects.get_or_create(
                name=kpi_data['name'],
                defaults=kpi_data
            )
            if created:
                self.stdout.write(f'  ✓ KPI "{kpi_data["display_name"]}" ایجاد شد')

    def create_dashboard(self):
        """ایجاد داشبورد اصلی"""
        self.stdout.write('🏠 ایجاد داشبورد مدیریتی...')
        
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('کاربر مدیر یافت نشد'))
            return
        
        dashboard, created = Dashboard.objects.get_or_create(
            name='داشبورد مدیریتی',
            defaults={
                'description': 'داشبورد اصلی برای مدیریت و کنترل عملکرد سیستم ژورقالای',
                'owner': admin_user,
                'is_public': True,
                'refresh_interval': 300,
                'layout_config': {
                    'grid_cols': 12,
                    'grid_rows': 8,
                    'compact_type': 'vertical'
                }
            }
        )
        
        if created:
            # اضافه کردن ویجت‌ها
            charts = Chart.objects.all()
            positions = [
                {'x': 0, 'y': 0, 'w': 6, 'h': 3},
                {'x': 6, 'y': 0, 'w': 6, 'h': 3},
                {'x': 0, 'y': 3, 'w': 4, 'h': 3},
                {'x': 4, 'y': 3, 'w': 4, 'h': 3},
                {'x': 8, 'y': 3, 'w': 4, 'h': 3},
                {'x': 0, 'y': 6, 'w': 12, 'h': 4},
            ]
            
            for i, chart in enumerate(charts[:6]):
                pos = positions[i] if i < len(positions) else {'x': 0, 'y': i*3, 'w': 6, 'h': 3}
                Widget.objects.create(
                    dashboard=dashboard,
                    chart=chart,
                    title=chart.name,
                    size='medium',
                    position_x=pos['x'],
                    position_y=pos['y'],
                    width=pos['w'],
                    height=pos['h'],
                    order=i
                )
            
            self.stdout.write('  ✓ داشبورد مدیریتی با موفقیت ایجاد شد') 