from django.db import models
from django.core.exceptions import ValidationError


class NonBazargahAllocation(models.Model):
    """مدل تخصیص آدرس برای خریدهای خارج بازارگاه"""
    
    purchase = models.ForeignKey(
        'major.NonBazargahPurchase', 
        on_delete=models.CASCADE, 
        verbose_name='خرید مرتبط',
        related_name='allocations'
    )
    
    # شناسه/شماره تخصیص
    allocation_number = models.CharField(
        "شماره تخصیص", 
        max_length=20, 
        blank=True, 
        null=True,
        help_text="شماره شناسایی تخصیص (اختیاری)"
    )
    
    # اطلاعات آدرس و تحویل
    delivery_address = models.TextField("آدرس تحویل", help_text="آدرس کامل محل تحویل")
    delivery_postal_code = models.CharField("کد پستی", max_length=10, help_text="کد پستی محل تحویل")
    delivery_receiver_name = models.CharField("نام گیرنده", max_length=255, help_text="نام شخص گیرنده کالا")
    coordination_phone = models.CharField("شماره هماهنگی", max_length=15, help_text="شماره تماس برای هماهنگی تحویل")
    
    # وزن تخصیص یافته
    allocated_weight = models.PositiveIntegerField("وزن تخصیص یافته (کیلوگرم)", help_text="وزن کالایی که به این آدرس تخصیص می‌یابد")

    # شماره حسابداری (برای خروجی فاکتور بارنامه)
    accounting_number = models.CharField("شماره حسابداری", max_length=50, blank=True, null=True)

    # توضیحات اضافی
    notes = models.TextField("توضیحات", blank=True, null=True, help_text="توضیحات اضافی در مورد این تخصیص")
    
    class Meta:
        verbose_name = "تخصیص آدرس خارج بازارگاه"
        verbose_name_plural = "تخصیص‌های آدرس خارج بازارگاه"
        ordering = ['-id']
    
    def __str__(self):
        if self.allocation_number:
            return f"تخصیص #{self.allocation_number} - {self.allocated_weight} کیلوگرم - {self.delivery_receiver_name}"
        return f"تخصیص {self.allocated_weight} کیلوگرم - {self.delivery_receiver_name}"
    
    def clean(self):
        """اعتبارسنجی مدل - فقط فیلدهای اساسی"""
        errors = {}
        
        # بررسی کد پستی
        if self.delivery_postal_code:
            postal_code = ''.join(c for c in str(self.delivery_postal_code) if c.isdigit())
            if len(postal_code) != 10:
                errors['delivery_postal_code'] = 'کد پستی باید 10 رقم باشد'
        
        # بررسی شماره تلفن
        if self.coordination_phone:
            phone = ''.join(c for c in str(self.coordination_phone) if c.isdigit())
            if len(phone) < 10:
                errors['coordination_phone'] = 'شماره تلفن باید حداقل 10 رقم باشد'
        
        # بررسی وزن - فقط بررسی مثبت بودن
        if self.allocated_weight and self.allocated_weight <= 0:
            errors['allocated_weight'] = 'وزن تخصیص یافته باید بزرگتر از صفر باشد'
        
        if errors:
            raise ValidationError(errors)
    
    def get_total_allocated_weight(self):
        """محاسبه مجموع وزن تخصیص‌های این خرید"""
        return NonBazargahAllocation.objects.filter(
            purchase=self.purchase
        ).aggregate(
            total=models.Sum('allocated_weight')
        )['total'] or 0
    
    def get_remaining_weight(self):
        """محاسبه وزن باقی‌مانده برای تخصیص"""
        total_allocated = self.get_total_allocated_weight()
        
        # بررسی اینکه purchase و quantity موجود باشد
        if not self.purchase or not self.purchase.quantity:
            return 0
        
        # تبدیل وزن درخواستی به کیلوگرم
        requested_weight_kg = self.purchase.quantity
        if self.purchase.unit == 'Ton':
            requested_weight_kg = self.purchase.quantity * 1000
        elif self.purchase.unit == 'Kiseh' and self.purchase.bag_weight:
            requested_weight_kg = self.purchase.quantity * self.purchase.bag_weight
        
        # اطمینان از اینکه هر دو مقدار عدد هستند
        if requested_weight_kg is None:
            requested_weight_kg = 0
        if total_allocated is None:
            total_allocated = 0
        
        return max(0, requested_weight_kg - total_allocated)
    
    def save(self, *args, **kwargs):
        # تولید شماره تخصیص خودکار (از 500000 شروع)
        if not self.allocation_number:
            # دریافت آخرین شماره تخصیص
            last_allocation = NonBazargahAllocation.objects.filter(
                allocation_number__isnull=False
            ).order_by('-allocation_number').first()
            
            if last_allocation and last_allocation.allocation_number:
                try:
                    last_number = int(last_allocation.allocation_number)
                    self.allocation_number = str(last_number + 1)
                except (ValueError, TypeError):
                    # اگر شماره قبلی عدد نبود، از 500000 شروع کن
                    self.allocation_number = '500000'
            else:
                # اولین تخصیص
                self.allocation_number = '500000'
        
        super().save(*args, **kwargs)