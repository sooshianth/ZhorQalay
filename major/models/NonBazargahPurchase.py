from django.db import models
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
    
    # فیلدهای مربوط به تخصیص آدرس
    assigned_warehouse_address = models.TextField("آدرس انبار تخصیص یافته", null=True, blank=True)
    assigned_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="تخصیص داده شده توسط", related_name='assigned_non_bazargah_purchases')
    assigned_at = models.DateTimeField("زمان تخصیص آدرس", null=True, blank=True)
    
    # فیلدهای مربوط به وزن‌گیری
    empty_weight = models.PositiveIntegerField("وزن خالی (کیلوگرم)", null=True, blank=True, help_text="وزن ماشین خالی")
    loaded_weight = models.PositiveIntegerField("وزن پر (کیلوگرم)", null=True, blank=True, help_text="وزن ماشین پر")
    delivered_weight = models.PositiveIntegerField("وزن تحویلی (کیلوگرم)", null=True, blank=True, help_text="وزن نهایی تحویل داده شده به مشتری")
    weight_difference = models.IntegerField("اختلاف وزن (کیلوگرم)", null=True, blank=True, help_text="اختلاف بین وزن درخواستی و تحویلی")
    
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
        """محاسبه اختلاف وزن بین درخواستی و تحویلی"""
        if self.delivered_weight and self.quantity:
            # تبدیل واحد بر اساس نوع واحد
            requested_weight_in_kg = self.quantity
            if self.unit == 'Ton':
                requested_weight_in_kg = self.quantity * 1000
            elif self.unit == 'Kiseh' and self.bag_weight:
                requested_weight_in_kg = self.quantity * self.bag_weight
            
            return self.delivered_weight - requested_weight_in_kg
        return None
    
    def can_verify_payment(self, user):
        """بررسی امکان تایید پرداخت"""
        # فقط مدیر مالی یا ادمین می‌توانند پرداخت را تایید کنند
        from core.decorators.det_user_role import determine_user_role
        user_role = determine_user_role(user)
        return user_role in ['financial_manager', 'admin'] and self.state in ['initiated', 'payment_verification_pending']
    
    def calculate_total_amount(self):
        """محاسبه مبلغ کل بر اساس مقدار و فی فروش"""
        if self.quantity and self.customer_price:
            # تبدیل واحد به کیلوگرم برای محاسبه
            quantity_in_kg = self.quantity
            if self.unit == 'Ton':
                quantity_in_kg = self.quantity * 1000
            elif self.unit == 'Kiseh' and self.bag_weight:
                quantity_in_kg = self.quantity * self.bag_weight
            
            return quantity_in_kg * self.customer_price
        return None

    def save(self, *args, **kwargs):
        # محاسبه مبلغ پرداختی خودکار
        calculated_amount = self.calculate_total_amount()
        if calculated_amount:
            self.amount_paid = calculated_amount
        
        # محاسبه اختلاف وزن هنگام ذخیره
        if self.delivered_weight and self.quantity:
            self.weight_difference = self.calculate_weight_difference()
        
        super().save(*args, **kwargs)