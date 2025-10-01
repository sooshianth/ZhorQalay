from django.db import models
from django.core.exceptions import ValidationError
from .BasePurchase import BasePurchase
from .NonBazargahProduct import NonBazargahProduct

class NonBazargahPurchase(BasePurchase):
    # Override customer field with specific related_name
    customer = models.ForeignKey('core.Customer', on_delete=models.CASCADE, verbose_name='مشتری', null=True, blank=True, related_name='non_bazargah_purchases_made')
    
    UNIT_CHOICES = [
        ('Kilo', 'کیلوگرم'),
        ('Ton', 'تن'),
        ('Kiseh', 'کیسه'),
    ]

    STATUS_CHOICES = [
        ('initiated', 'شروع شده'),
        ('payment_verification_pending', 'انتظار تایید پرداخت'),
        ('payment_verified', 'تایید پرداخت'),
        ('address_assigned', 'تخصیص آدرس'),
        ('sent_to_warehouse', 'ارسال به انبار'),
        ('carrier_notified', 'اعلام بار به باربری'),
        ('vehicle_arrived', 'ورود ماشین'),
        ('empty_weighed', 'وزن خالی ثبت شده'),
        ('loaded_weighed', 'وزن پر ثبت شده'),
        ('barnameh_issued', 'صدور بارنامه'),
        ('delivered', 'تحویل داده شده'),
        ('purchase_closed', 'بستن خرید'),
        ('canceled', 'لغو شده'),
        ('archived', 'آرشیو شده'),
    ]
    
    purchase_number = models.CharField("شماره خرید", max_length=7, blank=True, null=True, unique=True)
    product = models.ForeignKey(NonBazargahProduct, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="محصول", related_name="non_bazargah_purchases")
    unit = models.CharField(max_length=100, null=True, blank=True, verbose_name="واحد", choices=UNIT_CHOICES)
    quantity = models.PositiveIntegerField("مقدار", null=True, blank=True, help_text="مقدار خرید بر اساس واحد انتخاب شده")
    bag_weight = models.PositiveIntegerField("وزن کیسه (کیلوگرم)", null=True, blank=True, help_text="وزن هر کیسه در صورت انتخاب واحد کیسه")
    state = models.CharField(max_length=100, null=True, blank=True, verbose_name="وضعیت", default='initiated', choices=STATUS_CHOICES)
    
    # فیلدهای مربوط به تایید پرداخت
    payment_document = models.FileField("مدرک پرداخت", upload_to='non_bazargah_payment_docs/', null=True, blank=True, help_text="تصویر رسید یا مدرک پرداخت")
    payment_verified_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="تایید شده توسط", related_name='verified_non_bazargah_purchases')
    payment_verified_at = models.DateTimeField("زمان تایید پرداخت", null=True, blank=True)
    payment_notes = models.TextField("توضیحات پرداخت", null=True, blank=True)
    
    # فیلدهای مربوط به وزن‌گیری
    empty_weight = models.PositiveIntegerField("وزن خالی (کیلوگرم)", null=True, blank=True, help_text="وزن ماشین خالی")
    loaded_weight = models.PositiveIntegerField("وزن پر (کیلوگرم)", null=True, blank=True, help_text="وزن ماشین پر")
    delivered_weight = models.PositiveIntegerField("وزن تحویلی (کیلوگرم)", null=True, blank=True, help_text="وزن نهایی تحویل داده شده به مشتری")
    weight_difference = models.IntegerField("اختلاف وزن (کیلوگرم)", null=True, blank=True, help_text="اختلاف بین وزن درخواستی و تحویلی")
    weight_difference_amount = models.IntegerField("مبلغ اختلاف وزن (ریال)", null=True, blank=True, help_text="مبلغ اختلاف وزن بر اساس فی خرید")
    
    # فیلدهای مربوط به انبار و لجستیک
    warehouse_contact_person = models.CharField("نام رابط انبار", max_length=255, null=True, blank=True)
    warehouse_contact_phone = models.CharField("شماره تماس رابط انبار", max_length=15, null=True, blank=True)
    logistics_notes = models.TextField("یادداشت‌های لجستیک", null=True, blank=True)

    class Meta:
        verbose_name = "خرید خارج بازارگاه"
        verbose_name_plural = "خریدهای خارج بازارگاه"

    def __str__(self):
        return f"خرید: {self.purchase_number} - {self.product.name if self.product else 'Unknown Product'}"
    
    def get_net_weight(self):
        """محاسبه وزن خالص (وزن پر - وزن خالی)"""
        if self.loaded_weight and self.empty_weight:
            return self.loaded_weight - self.empty_weight
        return None
    
    def calculate_weight_difference(self):
        """محاسبه اختلاف وزن بین درخواستی و وزن خالص تحویلی"""
        if self.delivered_weight and self.empty_weight and self.quantity:
            # تبدیل واحد بر اساس نوع واحد
            requested_weight_in_kg = float(self.quantity)
            if self.unit == 'Ton':
                requested_weight_in_kg = float(self.quantity) * 1000
            elif self.unit == 'Kiseh' and self.bag_weight:
                requested_weight_in_kg = float(self.quantity) * float(self.bag_weight)
            
            # وزن خالص تحویلی = وزن تحویلی - وزن خالی
            net_delivered_weight = float(self.delivered_weight) - float(self.empty_weight)
            
            # اختلاف وزن = وزن خالص تحویلی - وزن سفارش
            return net_delivered_weight - requested_weight_in_kg
        return None
    
    def calculate_net_weight_difference(self):
        """محاسبه اختلاف وزن خالص (وزن تحویلی - وزن خالی - وزن سفارش)"""
        if self.delivered_weight and self.empty_weight and self.quantity:
            # تبدیل واحد بر اساس نوع واحد
            requested_weight_in_kg = float(self.quantity)
            if self.unit == 'Ton':
                requested_weight_in_kg = float(self.quantity) * 1000
            elif self.unit == 'Kiseh' and self.bag_weight:
                requested_weight_in_kg = float(self.quantity) * float(self.bag_weight)
            
            # وزن خالص تحویلی = وزن تحویلی - وزن خالی
            net_delivered_weight = float(self.delivered_weight) - float(self.empty_weight)
            
            # اختلاف وزن خالص = وزن خالص تحویلی - وزن سفارش
            return net_delivered_weight - requested_weight_in_kg
        return None
    
    def calculate_weight_difference_amount(self):
        """محاسبه مبلغ اختلاف وزن بر اساس فی خرید"""
        weight_difference = self.calculate_net_weight_difference()
        if weight_difference is not None and self.company_price:
            return float(weight_difference) * float(self.company_price)
        return None
    
    def add_weight_difference_to_customer_wallet(self):
        """اضافه کردن مبلغ اختلاف وزن به کیف پول مشتری"""
        if not self.customer:
            return None
            
        weight_difference_amount = self.calculate_weight_difference_amount()
        if weight_difference_amount is None or weight_difference_amount == 0:
            return None
        
        try:
            from fledger.models import Wallet, Transaction
            
            # دریافت یا ایجاد کیف پول مشتری
            wallet, created = Wallet.objects.get_or_create(
                customer=self.customer,
                defaults={
                    'description': f'کیف پول {self.customer.name}',
                    'balance': 0
                }
            )
            
            # تعیین نوع تراکنش بر اساس مثبت یا منفی بودن مبلغ
            if weight_difference_amount > 0:
                # اضافه تحویل - مشتری باید مبلغ اضافی بپردازد (بدهی)
                transaction_type = 'Hazinah'
                description = f'اضافه تحویل خرید {self.purchase_number} - اختلاف وزن: +{self.weight_difference} کیلوگرم'
            else:
                # کمبود تحویل - مشتری باید مبلغ کسر دریافت کند (درآمد)
                transaction_type = 'Income'
                description = f'کمبود تحویل خرید {self.purchase_number} - اختلاف وزن: {self.weight_difference} کیلوگرم'
            
            # ایجاد تراکنش
            transaction = Transaction.objects.create(
                wallet=wallet,
                transaction_type=transaction_type,
                amount=abs(float(weight_difference_amount)),  # مقدار مثبت
                description=description,
                status='approved',  # تایید خودکار
                created_by=None,  # سیستم
                approved_by=None,  # سیستم
            )
            
            # بروزرسانی موجودی کیف پول
            wallet.calculate_balance()
            
            return transaction
            
        except Exception as e:
            import logging
            logger = logging.getLogger('major_non_bazargah_crud')
            logger.error(f"خطا در اضافه کردن مبلغ اختلاف وزن به کیف پول مشتری {self.customer.id}: {str(e)}")
            return None
    
    def get_total_phish_amount(self):
        """محاسبه مجموع مبلغ فیش‌های پرداخت"""
        return self.phishes.aggregate(total=models.Sum('amount'))['total'] or 0
    
    def get_remaining_phish_amount(self):
        """محاسبه مبلغ باقی‌مانده که باید با فیش پوشش داده شود"""
        total_phish = self.get_total_phish_amount()
        if self.amount_paid:
            return max(0, self.amount_paid - total_phish)
        return 0
    
    def can_verify_payment(self, user):
        """بررسی امکان تایید پرداخت - باید مجموع فیش‌ها با مبلغ خرید برابر باشد"""
        # فقط مدیر مالی یا ادمین می‌توانند پرداخت را تایید کنند
        from core.decorators.det_user_role import determine_user_role
        user_role = determine_user_role(user)
        
        # بررسی نقش کاربر و وضعیت خرید
        if user_role not in ['financial_manager', 'admin']:
            return False
        
        if self.state not in ['initiated', 'payment_verification_pending']:
            return False
        
        # بررسی اینکه حداقل یک مدرک پرداخت آپلود شده باشد
        if not self.payment_documents.exists():
            return False
        
        # بررسی اینکه حداقل یک فیش وجود دارد
        if not self.phishes.exists():
            return False
        
        # بررسی اینکه مجموع فیش‌ها با مبلغ خرید برابر است
        total_phish = self.get_total_phish_amount()
        if self.amount_paid and total_phish >= self.amount_paid:
            return True
        
        return False
    
    def calculate_total_amount(self):
        """محاسبه مبلغ کل بر اساس مقدار و فی فروش"""
        if self.quantity and self.customer_price:
            # تبدیل واحد به کیلوگرم برای محاسبه
            quantity_in_kg = float(self.quantity)
            if self.unit == 'Ton':
                quantity_in_kg = float(self.quantity) * 1000
            elif self.unit == 'Kiseh' and self.bag_weight:
                quantity_in_kg = float(self.quantity) * float(self.bag_weight)
            
            return quantity_in_kg * self.customer_price
        return None
    
    def get_total_allocated_weight(self):
        """محاسبه مجموع وزن تخصیص‌های این خرید"""
        return self.allocations.aggregate(
            total=models.Sum('allocated_weight')
        )['total'] or 0
    
    def get_remaining_weight_for_allocation(self):
        """محاسبه وزن باقی‌مانده برای تخصیص"""
        total_allocated = self.get_total_allocated_weight()
        
        # بررسی اینکه quantity موجود باشد
        if not self.quantity:
            return 0
        
        # تبدیل وزن درخواستی به کیلوگرم
        requested_weight_kg = float(self.quantity)
        if self.unit == 'Ton':
            requested_weight_kg = float(self.quantity) * 1000
        elif self.unit == 'Kiseh' and self.bag_weight:
            requested_weight_kg = float(self.quantity) * float(self.bag_weight)
        
        # اطمینان از اینکه هر دو مقدار عدد هستند
        if requested_weight_kg is None:
            requested_weight_kg = 0
        if total_allocated is None:
            total_allocated = 0
        
        return max(0, requested_weight_kg - total_allocated)
    
    def can_assign_addresses(self):
        """بررسی امکان تخصیص آدرس"""
        return self.state == 'payment_verified'
    
    def can_approve_addresses(self):
        """بررسی امکان تایید آدرس‌ها"""
        if self.state != 'payment_verified':
            return False
        
        # بررسی اینکه آیا همه وزن تخصیص شده است
        remaining_weight = self.get_remaining_weight_for_allocation()
        return remaining_weight == 0 and self.allocations.exists()
    
    def approve_all_allocations(self):
        """تایید همه تخصیص‌ها و تغییر وضعیت خرید"""
        if not self.can_approve_addresses():
            raise ValidationError('امکان تایید آدرس‌ها وجود ندارد')
        
        # تغییر وضعیت خرید
        self.state = 'address_assigned'
        self.save()

    def get_product_purchase_price(self):
        """دریافت فی خرید از محصول"""
        if self.product:
            return self.product.get_purchase_price()
        return 0
    
    def get_all_barnamehs(self):
        """دریافت تمام بارنامه‌های مرتبط با این خرید (از طریق تخصیص‌ها و مستقیم)"""
        from bki_barnameh.models.BarnamehModel import Barnameh
        
        barnamehs = []
        barnameh_ids = set()  # برای جلوگیری از تکرار
        
        # بارنامه‌های مرتبط از طریق تخصیص‌ها
        for allocation in self.allocations.all():
            for barnameh in allocation.barnamehs.all():
                if barnameh.id not in barnameh_ids:
                    barnamehs.append(barnameh)
                    barnameh_ids.add(barnameh.id)
        
        # بارنامه‌های مستقیم (legacy) - فقط اگر قبلاً اضافه نشده باشند
        direct_barnamehs = Barnameh.objects.filter(non_bazargah_purchase=self)
        for barnameh in direct_barnamehs:
            if barnameh.id not in barnameh_ids:
                barnamehs.append(barnameh)
                barnameh_ids.add(barnameh.id)
        
        return barnamehs
    
    def can_confirm_vehicle_arrival(self):
        """بررسی امکان تایید ورود ماشین - باید برای همه تخصیص‌ها حداقل یک بارنامه وجود داشته باشد"""
        if self.state != 'carrier_notified':
            return False
        
        allocations = self.allocations.all()
        if not allocations.exists():
            return False
        
        # برای هر تخصیص حداقل یک بارنامه باید وجود داشته باشد
        for allocation in allocations:
            if not allocation.barnamehs.exists():
                return False
        
        return True
    
    def can_record_empty_weight(self):
        """بررسی امکان ثبت وزن خالی - همه بارنامه‌ها باید اطلاعات ماشین کاملی داشته باشند"""
        if self.state != 'vehicle_arrived':
            return False
        
        barnamehs = self.get_all_barnamehs()
        if not barnamehs:
            return False
        
        # همه بارنامه‌ها باید اطلاعات ماشین کامل داشته باشند
        for barnameh in barnamehs:
            if not (barnameh.driver_name and barnameh.driver_phone and barnameh.vehicle_plate):
                return False
        
        return True
    
    def can_record_empty_weight_values(self):
        """بررسی امکان ثبت وزن خالی - همه بارنامه‌ها باید وزن خالی داشته باشند"""
        if self.state != 'vehicle_arrived':
            return False
        
        barnamehs = self.get_all_barnamehs()
        if not barnamehs:
            return False
        
        # همه بارنامه‌ها باید وزن خالی داشته باشند (مقدار بیشتر از صفر)
        for barnameh in barnamehs:
            if not barnameh.empty_vehicle_weight or barnameh.empty_vehicle_weight <= 0:
                return False
        
        return True
    
    def can_record_loaded_weight(self):
        """بررسی امکان ثبت وزن پر - همه بارنامه‌ها باید وزن خالی داشته باشند"""
        if self.state != 'empty_weighed':
            return False
        
        barnamehs = self.get_all_barnamehs()
        if not barnamehs:
            return False
        
        # همه بارنامه‌ها باید وزن خالی داشته باشند
        for barnameh in barnamehs:
            if not barnameh.empty_vehicle_weight:
                return False
        
        return True
    
    def can_record_loaded_weight_values(self):
        """بررسی امکان ثبت وزن پر - همه بارنامه‌ها باید وزن پر داشته باشند"""
        if self.state != 'empty_weighed':
            return False
        
        barnamehs = self.get_all_barnamehs()
        if not barnamehs:
            return False
        
        # همه بارنامه‌ها باید وزن پر داشته باشند (مقدار بیشتر از صفر)
        for barnameh in barnamehs:
            if not barnameh.loaded_vehicle_weight or barnameh.loaded_vehicle_weight <= 0:
                return False
        
        return True
    
    def can_issue_barnameh(self):
        """بررسی امکان صدور بارنامه - همه بارنامه‌ها باید وزن پر داشته باشند"""
        if self.state != 'loaded_weighed':
            return False
        
        barnamehs = self.get_all_barnamehs()
        if not barnamehs:
            return False
        
        # همه بارنامه‌ها باید وزن پر داشته باشند (مقدار بیشتر از صفر)
        for barnameh in barnamehs:
            if not barnameh.loaded_vehicle_weight or barnameh.loaded_vehicle_weight <= 0:
                return False
        
        return True
    
    def calculate_total_weights_from_barnamehs(self):
        """محاسبه مجموع وزن‌ها از بارنامه‌ها"""
        barnamehs = self.get_all_barnamehs()
        if not barnamehs:
            return {
                'total_empty_weight': 0,
                'total_loaded_weight': 0,
                'total_delivered_weight': 0
            }
        
        total_empty_weight = 0
        total_loaded_weight = 0
        total_delivered_weight = 0
        
        for barnameh in barnamehs:
            if barnameh.empty_vehicle_weight:
                total_empty_weight += float(barnameh.empty_vehicle_weight)
            if barnameh.loaded_vehicle_weight:
                total_loaded_weight += float(barnameh.loaded_vehicle_weight)
            if barnameh.final_delivered_weight:
                total_delivered_weight += float(barnameh.final_delivered_weight)
        
        return {
            'total_empty_weight': int(total_empty_weight),
            'total_loaded_weight': int(total_loaded_weight),
            'total_delivered_weight': int(total_delivered_weight)
        }
    
    def update_weights_from_barnamehs(self, save=True):
        """بروزرسانی وزن‌های خرید از مجموع وزن‌های بارنامه‌ها"""
        weights = self.calculate_total_weights_from_barnamehs()
        
        self.empty_weight = weights['total_empty_weight']
        self.loaded_weight = weights['total_loaded_weight']
        self.delivered_weight = weights['total_delivered_weight']
        
        # محاسبه اختلاف وزن (وزن خالص تحویلی - وزن سفارش)
        if self.delivered_weight and self.empty_weight and self.quantity:
            self.weight_difference = self.calculate_weight_difference()
        
        if save:
            self.save()

    def save(self, *args, **kwargs):
        # تولید شماره خرید خودکار (از 100000 شروع)
        if not self.purchase_number:
            # دریافت آخرین شماره خرید
            last_purchase = NonBazargahPurchase.objects.filter(
                purchase_number__isnull=False
            ).order_by('-purchase_number').first()
            
            if last_purchase and last_purchase.purchase_number:
                try:
                    last_number = int(last_purchase.purchase_number)
                    self.purchase_number = str(last_number + 1)
                except (ValueError, TypeError):
                    # اگر شماره قبلی عدد نبود، از 100000 شروع کن
                    self.purchase_number = '100000'
            else:
                # اولین خرید
                self.purchase_number = '100000'
        
        # تنظیم فی خرید از محصول
        if self.product and not self.company_price:
            self.company_price = self.get_product_purchase_price()
        
        # محاسبه مبلغ پرداختی خودکار
        calculated_amount = self.calculate_total_amount()
        if calculated_amount:
            self.amount_paid = calculated_amount
        
        # محاسبه اختلاف وزن هنگام ذخیره (وزن خالص تحویلی - وزن سفارش)
        if self.delivered_weight and self.empty_weight and self.quantity:
            self.weight_difference = self.calculate_weight_difference()
        
        super().save(*args, **kwargs)