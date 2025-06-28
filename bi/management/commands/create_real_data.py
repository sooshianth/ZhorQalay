from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, datetime
import random
from django.apps import apps

# Import models
from core.CustomerModel import Customer, PhoneNumber, ActivityField, ProductPreference, PaymentPreference
from core.PurchaseModel import Purchase
from core.CargoProductModel import CargoProduct, VaredKonandeh, Barbary
from core.SalesAgentModel import SalesAgent

class Command(BaseCommand):
    help = 'ایجاد داده‌های واقعی برای سیستم BI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-data',
            action='store_true',
            help='حذف داده‌های قبلی',
        )
        parser.add_argument(
            '--customers',
            type=int,
            default=200,
            help='تعداد مشتریان برای ایجاد',
        )
        parser.add_argument(
            '--purchases',
            type=int,
            default=500,
            help='تعداد خریدها برای ایجاد',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 شروع ایجاد داده‌های واقعی...'))
        
        if options['clear_data']:
            self.clear_existing_data()
        
        # ایجاد یا دریافت کاربران مورد نیاز
        self.create_users()
        
        # ایجاد واردکنندگان و باربری‌ها
        self.create_vendors_and_transporters()
        
        # ایجاد محصولات واقعی
        self.create_real_products()
        
        # ایجاد مشتریان واقعی
        self.create_real_customers(options['customers'])
        
        # ایجاد خریدهای واقعی
        self.create_real_purchases(options['purchases'])
        
        self.stdout.write(self.style.SUCCESS('✅ ایجاد داده‌های واقعی با موفقیت انجام شد!'))

    def clear_existing_data(self):
        """حذف داده‌های قبلی"""
        self.stdout.write('🗑️ حذف داده‌های قبلی...')
        
        Purchase.objects.all().delete()
        Customer.objects.all().delete()
        CargoProduct.objects.all().delete()
        VaredKonandeh.objects.all().delete()
        Barbary.objects.all().delete()
        
        self.stdout.write('  ✓ داده‌های قبلی حذف شدند')

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
            {'username': 'sales_manager', 'first_name': 'احمد', 'last_name': 'کریمی'},
            {'username': 'sales_agent_1', 'first_name': 'فاطمه', 'last_name': 'احمدی'},
            {'username': 'sales_agent_2', 'first_name': 'محمد', 'last_name': 'رضایی'},
            {'username': 'sales_agent_3', 'first_name': 'زهرا', 'last_name': 'محمدی'},
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
                        'phone_number': f'091{random.randint(10000000, 99999999)}'
                    }
                )
                self.stdout.write(f'  ✓ کارشناس فروش {agent_data["first_name"]} {agent_data["last_name"]} ایجاد شد')

    def create_vendors_and_transporters(self):
        """ایجاد واردکنندگان و باربری‌ها"""
        self.stdout.write('🚛 ایجاد واردکنندگان و باربری‌ها...')
        
        # واردکنندگان واقعی
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
            self.stdout.write(f'  ✓ واردکننده {vendor_data["name"]} ایجاد شد')
        
        # باربری‌ها
        transporters_data = [
            {'name': 'باربری اطلس', 'phone': '09121234567', 'desc': 'حمل و نقل سراسر کشور'},
            {'name': 'باربری پارس', 'phone': '09122345678', 'desc': 'تخصص در حمل غلات'},
            {'name': 'باربری سپهر', 'phone': '09123456789', 'desc': 'باربری مطمئن'},
            {'name': 'باربری فردوس', 'phone': '09124567890', 'desc': 'سرویس 24 ساعته'},
            {'name': 'باربری آریا', 'phone': '09125678901', 'desc': 'حمل سریع و ایمن'},
        ]
        
        for trans_data in transporters_data:
            Barbary.objects.get_or_create(
                name=trans_data['name'],
                defaults={
                    'phone_number': trans_data['phone'],
                    'description': trans_data['desc'],
                    'email': f"info@{trans_data['name'].replace(' ', '').lower()}.com"
                }
            )
            self.stdout.write(f'  ✓ باربری {trans_data["name"]} ایجاد شد')

    def create_real_products(self):
        """ایجاد محصولات واقعی"""
        self.stdout.write('🌾 ایجاد محصولات واقعی...')
        
        vendors = list(VaredKonandeh.objects.all())
        barbaries = list(Barbary.objects.all())
        
        # محصولات واقعی با قیمت‌های بازار
        products_data = [
            # کنجاله سویا
            {'type': 'bazaargah', 'cottage': '12345001', 'product': 'soy_meal', 'country': 'argentina', 
             'company_price': 175000, 'customer_price': 185000, 'weight': 25000000, 'port': 'امام خمینی'},
            {'type': 'bazaargah', 'cottage': '12345002', 'product': 'soy_meal', 'country': 'brazil', 
             'company_price': 172000, 'customer_price': 182000, 'weight': 30000000, 'port': 'امام خمینی'},
            {'type': 'bazaargah', 'cottage': '12345003', 'product': 'soy_meal', 'country': 'argentina', 
             'company_price': 178000, 'customer_price': 188000, 'weight': 20000000, 'port': 'شهید رجایی'},
            
            # ذرت
            {'type': 'bazaargah', 'cottage': '12345004', 'product': 'corn', 'country': 'ukraine', 
             'company_price': 155000, 'customer_price': 165000, 'weight': 40000000, 'port': 'امام خمینی'},
            {'type': 'bazaargah', 'cottage': '12345005', 'product': 'corn', 'country': 'brazil', 
             'company_price': 152000, 'customer_price': 162000, 'weight': 35000000, 'port': 'امام خمینی'},
            {'type': 'bazaargah', 'cottage': '12345006', 'product': 'corn', 'country': 'argentina', 
             'company_price': 158000, 'customer_price': 168000, 'weight': 25000000, 'port': 'شهید رجایی'},
            
            # جو
            {'type': 'bazaargah', 'cottage': '12345007', 'product': 'barley', 'country': 'russia', 
             'company_price': 135000, 'customer_price': 145000, 'weight': 30000000, 'port': 'انزلی'},
            {'type': 'bazaargah', 'cottage': '12345008', 'product': 'barley', 'country': 'kazakhstan', 
             'company_price': 132000, 'customer_price': 142000, 'weight': 28000000, 'port': 'انزلی'},
            {'type': 'bazaargah', 'cottage': '12345009', 'product': 'barley', 'country': 'ukraine', 
             'company_price': 138000, 'customer_price': 148000, 'weight': 22000000, 'port': 'بهشهر'},
            
            # محصولات غیربازارگاه
            {'type': 'non_bazaargah', 'cottage': '901', 'product': 'soy_meal', 'country': 'iran', 
             'company_price': 190000, 'customer_price': 200000, 'weight': 15000000, 'port': 'سایر'},
            {'type': 'non_bazaargah', 'cottage': '902', 'product': 'corn', 'country': 'iran', 
             'company_price': 170000, 'customer_price': 180000, 'weight': 12000000, 'port': 'سایر'},
            {'type': 'non_bazaargah', 'cottage': '903', 'product': 'barley', 'country': 'iran', 
             'company_price': 150000, 'customer_price': 160000, 'weight': 18000000, 'port': 'سایر'},
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
            self.stdout.write(f'  ✓ محصول {product_data["cottage"]} ایجاد شد')

    def create_real_customers(self, count):
        """ایجاد مشتریان واقعی"""
        self.stdout.write(f'👥 ایجاد {count} مشتری واقعی...')
        
        # نام‌های واقعی ایرانی
        first_names = [
            'احمد', 'محمد', 'علی', 'حسن', 'حسین', 'مهدی', 'رضا', 'کریم',
            'فاطمه', 'زهرا', 'مریم', 'فهیمه', 'سکینه', 'زینب', 'طاهره', 'معصومه',
            'عباس', 'جعفر', 'موسی', 'یوسف', 'داود', 'سلیمان', 'ابراهیم', 'اسماعیل',
            'خدیجه', 'عایشه', 'صدیقه', 'ام کلثوم', 'رقیه', 'کوثر', 'فروغ', 'شهرزاد'
        ]
        
        last_names = [
            'احمدی', 'محمدی', 'علوی', 'حسینی', 'موسوی', 'رضایی', 'کریمی', 'نوری',
            'صادقی', 'باقری', 'جعفری', 'طاهری', 'شریفی', 'فرهادی', 'کاظمی', 'مرادی',
            'اسدی', 'قاسمی', 'یوسفی', 'ابراهیمی', 'داودی', 'سلیمانی', 'اسماعیلی', 'حیدری',
            'زارعی', 'کشاورز', 'تاجر', 'بازرگان', 'صنعتگر', 'حرفه‌ای', 'استادی', 'دانشمند'
        ]
        
        # شهرهای ایران
        cities = [
            'تهران', 'مشهد', 'اصفهان', 'کرج', 'شیراز', 'تبریز', 'قم', 'اهواز',
            'کرمانشاه', 'ارومیه', 'رشت', 'زاهدان', 'کرمان', 'همدان', 'یزد', 'اردبیل',
            'بندرعباس', 'آبادان', 'زنجان', 'سنندج', 'قزوین', 'خرم‌آباد', 'گرگان', 'ساری',
            'بیرجند', 'بوشهر', 'سمنان', 'ایلام', 'شهرکرد', 'یاسوج', 'کاشان', 'نجف‌آباد',
            'ورامین', 'اسلام‌شهر', 'بهشهر', 'گنبد', 'آمل', 'بابل', 'قائم‌شهر', 'ساوه'
        ]
        
        # دریافت sales agents
        sales_agents = list(SalesAgent.objects.all())
        
        # ایجاد ActivityField ها
        activity_fields = []
        for code, display in [
            ('chicken', 'مرغدار'),
            ('livestock', 'دامدار'),
            ('factory', 'کارخانه خوراک'),
            ('fish', 'پرورش آبزیان'),
            ('corporation', 'تعاونی'),
            ('dealer', 'دلال'),
            ('other', 'سایر')
        ]:
            field, created = ActivityField.objects.get_or_create(code=code)
            activity_fields.append(field)
        
        # ایجاد PaymentPreference ها
        payment_prefs = []
        for code, display in [
            ('cash', 'نقدی'),
            ('check', 'چک'),
            ('credit', 'اعتباری'),
            ('bazaargah', 'بازارگاه')
        ]:
            pref, created = PaymentPreference.objects.get_or_create(code=code)
            payment_prefs.append(pref)
        
        # ایجاد ProductPreference ها
        product_prefs = []
        for code, display in [
            ('soy_meal', 'کنجاله سویا'),
            ('corn', 'ذرت'),
            ('barley', 'جو')
        ]:
            pref, created = ProductPreference.objects.get_or_create(code=code)
            product_prefs.append(pref)
        
        for i in range(count):
            # ایجاد نام کامل
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            full_name = f'{first_name} {last_name}'
            
            # تولید شماره تلفن واقعی
            phone_number = f'9{random.randint(100000000, 999999999)}'
            
            # ایجاد مشتری
            customer = Customer.objects.create(
                name=full_name,
                city=random.choice(cities),
                phone_number=phone_number,  # برای سازگاری
                whatsapp_preference=random.choice([True, False]),
                sms_preference=random.choice([True, True, True, False]),  # 75% احتمال True
                is_bazaargah_enjoyer=random.choice([True, True, False]),  # 67% احتمال True
                is_favorite=random.choice([True, False, False, False]),  # 25% احتمال True
                is_active=True,
                contact_start_time=f'{random.randint(8, 10)}:00',
                contact_end_time=f'{random.randint(18, 20)}:00',
                quota=f'{random.randint(5, 50)} تن در ماه',
                added_description=f'مشتری {random.choice(["قدیمی", "جدید", "مهم", "VIP", "عادی"])} - {random.choice(["مرغداری", "دامداری", "کارخانه خوراک"])}'
            )
            
            # اضافه کردن شماره تلفن اصلی
            PhoneNumber.objects.create(
                customer=customer,
                number=phone_number,
                is_primary=True,
                sms_enabled=customer.sms_preference,
                description='شماره اصلی'
            )
            
            # گاهی شماره دوم اضافه کنیم
            if random.random() < 0.3:  # 30% احتمال
                second_phone = f'9{random.randint(100000000, 999999999)}'
                PhoneNumber.objects.create(
                    customer=customer,
                    number=second_phone,
                    is_primary=False,
                    sms_enabled=random.choice([True, False]),
                    description='شماره ثانویه'
                )
            
            # تخصیص کارشناس فروش
            if sales_agents:
                assigned_agents = random.sample(sales_agents, random.randint(1, min(2, len(sales_agents))))
                customer.sales_agent.set(assigned_agents)
            
            # اضافه کردن حیطه فعالیت
            customer_activities = random.sample(activity_fields, random.randint(1, 3))
            customer.field_of_activity.set(customer_activities)
            
            # اضافه کردن ترجیحات پرداخت
            customer_payments = random.sample(payment_prefs, random.randint(1, 2))
            customer.purchase_preferences.set(customer_payments)
            
            # اضافه کردن ترجیحات محصول
            customer_products = random.sample(product_prefs, random.randint(1, 3))
            customer.product_preferences.set(customer_products)
            
            if (i + 1) % 50 == 0:
                self.stdout.write(f'  ✓ {i + 1} مشتری ایجاد شد')
        
        self.stdout.write(f'  ✓ مجموعاً {count} مشتری واقعی ایجاد شد')

    def create_real_purchases(self, count):
        """ایجاد خریدهای واقعی"""
        self.stdout.write(f'💰 ایجاد {count} خرید واقعی...')
        
        customers = list(Customer.objects.all())
        products = list(CargoProduct.objects.all())
        sales_agents = list(SalesAgent.objects.all())
        
        if not customers or not products:
            self.stdout.write(self.style.ERROR('ابتدا مشتریان و محصولات را ایجاد کنید'))
            return
        
        # وضعیت‌های مختلف برای خریدها
        states = [
            'PAYMENT_VERIFIED',
            'ALLOCATION_APPROVED', 
            'ADDRESS_SENT',
            'WAITING_FOR_BARNAMEH',
            'BARNAMEH_ISSUED',
            'PURCHASE_CLOSED',
            'FULLY_SETTLED',
            'INVOICE_ISSUED'
        ]
        
        # شهرهای ایران برای آدرس
        addresses = [
            'تهران، خیابان ولیعصر، کوچه شهید احمدی، پلاک ۱۲۳',
            'مشهد، بلوار وکیل‌آباد، خیابان امام رضا، پلاک ۴۵۶',
            'اصفهان، خیابان چهارباغ، کوچه گلستان، پلاک ۷۸۹',
            'شیراز، خیابان زند، کوچه حافظ، پلاک ۱۰۱',
            'تبریز، خیابان امام خمینی، کوچه شریعتی، پلاک ۲۰۲',
            'کرج، بلوار طالقانی، خیابان شهید بهشتی، پلاک ۳۰۳',
            'قم، خیابان صفائیه، کوچه معلم، پلاک ۴۰۴',
            'اهواز، خیابان کیانپارس، کوچه پاسداران، پلاک ۵۰۵'
        ]
        
        for i in range(count):
            customer = random.choice(customers)
            product = random.choice(products)
            
            # محاسبه وزن و مبلغ واقعی
            order_weight = random.randint(10000, 100000)  # بین 10 تا 100 تن
            amount_paid = order_weight * product.customer_price
            
            # ایجاد شماره خرید برای خریدهای بازارگاه
            purchase_number = None
            if product.type == 'bazaargah':
                purchase_number = str(random.randint(1000000, 9999999))
            
            # تولید کد ملی و شماره‌های تلفن
            code_melli = f'{random.randint(1000000000, 9999999999)}'
            bazaargah_phone = customer.get_primary_phone()
            tahvil_phone = f'9{random.randint(100000000, 999999999)}'
            
            # تاریخ خرید در ۶ ماه گذشته
            days_ago = random.randint(1, 180)
            purchase_date = timezone.now() - timedelta(days=days_ago)
            
            purchase = Purchase.objects.create(
                customer=customer,
                cargo=product,
                state=random.choice(states),
                type=product.type,
                order_weight=order_weight,
                delivered_weight=order_weight - random.randint(0, 1000),  # کمی کسری
                amount_paid=amount_paid,
                company_price=product.company_price,
                customer_price=product.customer_price,
                payment_method=random.choice(['نقدی', 'توافقی']),
                purchase_number=purchase_number,
                tracking_number=str(random.randint(100000, 999999)) if purchase_number else None,
                shenase_takhsis=f'TKH{random.randint(100000, 999999)}' if purchase_number else None,
                code_melli_tahvil=code_melli,
                bazaargah_phone_number=bazaargah_phone,
                tahvil_phone_number=tahvil_phone,
                buyer_name=customer.name,
                address=random.choice(addresses),
                description=f'خرید {product.get_product_type_display()} از {product.get_country_display()}',
                priority=random.choice(['low', 'medium', 'high']),
                is_urgent=random.choice([True, False, False, False]),  # 25% احتمال
                created_at=purchase_date,
                updated_at=purchase_date + timedelta(hours=random.randint(1, 24))
            )
            
            # تخصیص کارشناس فروش
            if sales_agents:
                assigned_agent = random.choice(sales_agents)
                purchase.unique_sales_agent = assigned_agent
                purchase.unique_sales_agent_code = assigned_agent.user.username
                purchase.save()
            
            # اضافه کردن اختلاف برای برخی خریدها
            if random.random() < 0.3:  # 30% احتمال اختلاف
                purchase.extelaf_type = random.choice(['کسری', 'سرک'])
                purchase.extelaf_weight = random.randint(100, 2000)
                purchase.extelaf_amount = purchase.extelaf_weight * product.customer_price
                purchase.save()
            
            if (i + 1) % 100 == 0:
                self.stdout.write(f'  ✓ {i + 1} خرید ایجاد شد')
        
        self.stdout.write(f'  ✓ مجموعاً {count} خرید واقعی ایجاد شد') 