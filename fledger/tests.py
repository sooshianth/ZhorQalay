from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from core.CargoProductModel import VaredKonandeh, CargoProduct
from core.PurchaseModel import Purchase
from core.CustomerModel import Customer
from fledger.models import Wallet, Transaction, LedgerEntry


class FledgerTestCase(TestCase):
    def setUp(self):
        """تنظیمات اولیه برای تست‌ها"""
        
        # ایجاد کاربر
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # ایجاد واردکننده
        self.varedkonandeh = VaredKonandeh.objects.create(
            name='تست واردکننده',
            phone_number='09123456789',
            email='test@example.com'
        )
        
        # ایجاد محصول
        self.cargo = CargoProduct.objects.create(
            vared_konandeh=self.varedkonandeh,
            product_type='rice',
            country='india',
            weight=10000,
            company_price=50000,
            customer_price=55000
        )
        
        # ایجاد مشتری
        self.customer = Customer.objects.create(
            name='مشتری تست',
            phone_number='09121234567'
        )

    def test_wallet_creation(self):
        """تست ایجاد کیف پول"""
        wallet = Wallet.objects.create(
            varedkonandeh=self.varedkonandeh,
            description='تست کیف پول'
        )
        
        self.assertEqual(wallet.varedkonandeh.name, 'تست واردکننده')
        self.assertEqual(wallet.balance, 0)

    def test_transaction_creation(self):
        """تست ایجاد تراکنش"""
        wallet = Wallet.objects.create(varedkonandeh=self.varedkonandeh)
        
        transaction = Transaction.objects.create(
            wallet=wallet,
            transaction_type='deposit',
            amount=1000000,
            description='تست واریز',
            created_by=self.user
        )
        
        self.assertEqual(transaction.status, 'pending')
        self.assertEqual(transaction.amount, 1000000)

    def test_balance_calculation(self):
        """تست محاسبه موجودی کیف پول"""
        wallet = Wallet.objects.create(varedkonandeh=self.varedkonandeh)
        
        # ایجاد تراکنش تایید شده
        Transaction.objects.create(
            wallet=wallet,
            transaction_type='deposit',
            amount=2000000,
            status='approved',
            created_by=self.user
        )
        
        # محاسبه موجودی
        balance = wallet.calculate_balance()
        self.assertEqual(balance, 2000000)

    def test_ledger_entry_creation(self):
        """تست ایجاد ثبت دفتر"""
        # ایجاد خرید
        purchase = Purchase.objects.create(
            customer=self.customer,
            cargo=self.cargo,
            order_weight=1000,
            delivered_weight=950,
            company_price=50000,
            customer_price=55000,
            is_address_sent='1',
            wallet_index='0'  # بر اساس وزن سفارش
        )
        
        # ایجاد ثبت دفتر
        entry = LedgerEntry.create_or_update_entry(purchase)
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.weight, 1000)  # وزن سفارش
        self.assertEqual(entry.total_amount, 1000 * 50000)  # وزن × فی

    def test_wallet_index_calculation(self):
        """تست محاسبه بر اساس wallet_index"""
        # تست با wallet_index = '0' (وزن سفارش)
        purchase1 = Purchase.objects.create(
            customer=self.customer,
            cargo=self.cargo,
            order_weight=1000,
            delivered_weight=950,
            company_price=50000,
            is_address_sent='1',
            wallet_index='0'
        )
        
        entry1 = LedgerEntry.create_or_update_entry(purchase1)
        self.assertEqual(entry1.weight, 1000)
        
        # تست با wallet_index = '1' (وزن تحویلی)
        purchase2 = Purchase.objects.create(
            customer=self.customer,
            cargo=self.cargo,
            order_weight=1000,
            delivered_weight=950,
            company_price=50000,
            is_address_sent='1',
            wallet_index='1'
        )
        
        entry2 = LedgerEntry.create_or_update_entry(purchase2)
        self.assertEqual(entry2.weight, 950)

    def test_purchase_without_address_sent(self):
        """تست خرید بدون ارسال آدرس"""
        purchase = Purchase.objects.create(
            customer=self.customer,
            cargo=self.cargo,
            order_weight=1000,
            company_price=50000,
            is_address_sent='0'  # آدرس ارسال نشده
        )
        
        # باید هیچ ثبت دفتری ایجاد نشود
        entry = LedgerEntry.create_or_update_entry(purchase)
        self.assertIsNone(entry)

    def test_wallet_balance_with_purchases(self):
        """تست موجودی کیف پول با خریدها"""
        wallet = Wallet.objects.create(varedkonandeh=self.varedkonandeh)
        
        # اضافه کردن تراکنش مثبت
        Transaction.objects.create(
            wallet=wallet,
            transaction_type='deposit',
            amount=5000000,
            status='approved',
            created_by=self.user
        )
        
        # اضافه کردن خرید
        Purchase.objects.create(
            customer=self.customer,
            cargo=self.cargo,
            order_weight=1000,
            company_price=50000,
            is_address_sent='1',
            wallet_index='0'
        )
        
        # محاسبه موجودی
        balance = wallet.calculate_balance()
        
        # موجودی = 5,000,000 - (1000 × 50,000) = 0
        expected_balance = 5000000 - (1000 * 50000)
        self.assertEqual(balance, expected_balance)

    def test_purchase_summary(self):
        """تست خلاصه خریدها"""
        wallet = Wallet.objects.create(varedkonandeh=self.varedkonandeh)
        
        # ایجاد چند خرید
        for i in range(3):
            Purchase.objects.create(
                customer=self.customer,
                cargo=self.cargo,
                order_weight=1000,
                delivered_weight=950,
                company_price=50000,
                is_address_sent='1'
            )
        
        summary = wallet.get_purchase_summary()
        
        self.assertEqual(summary['total_purchases'], 3)
        self.assertEqual(summary['total_order_weight'], 3000)
        self.assertEqual(summary['total_delivered_weight'], 2850) 