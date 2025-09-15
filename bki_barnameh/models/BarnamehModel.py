from django.db import models
from django_jalali.db import models as jmodels
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.PurchaseModel import Purchase, ShenaseTakhsis

import logging

logger = logging.getLogger('bki_barnameh_models')

class Barnameh(models.Model):
    STATUS_CHOICES = [
        ('NOT_SENT_TO_BKI', 'ارسال نشده به بازارگاه'),
        ('SENT_TO_BKI', 'ارسال شده به بازارگاه'),
    ]
    file = models.FileField(upload_to='barnameh_files/', verbose_name='فایل برنامه', null=True, blank=True)

    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='barnamehs', verbose_name='خرید', null=True, blank=True)
    purchase_number = models.CharField(max_length=255, verbose_name='شناسه خرید', null=True, blank=True)
    shenase_takhsis = models.ForeignKey(ShenaseTakhsis, on_delete=models.CASCADE, related_name='barnameh', verbose_name='شناسه تخصیص', null=True, blank=True)
    shenase_takhsis_code = models.CharField(max_length=255, verbose_name='عدد شناسه تخصیص', null=True, blank=True)

    number = models.CharField(max_length=255, verbose_name='شماره بارنامه', null=True, blank=True, unique=True)
    serial = models.CharField(max_length=255, verbose_name='سریال بارنامه', null=True, blank=True)
    tonnage = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='وزن', null=True, blank=True)
    driver_phone = models.CharField(max_length=255, verbose_name='شماره تلفن راننده', null=True, blank=True)
    driver_name = models.CharField(max_length=255, verbose_name='نام راننده', null=True, blank=True)
    vehicle_plate = models.CharField(max_length=255, verbose_name='پلاک خودرو', null=True, blank=True)
    receiver_name = models.CharField(max_length=255, verbose_name='نام گیرنده', null=True, blank=True)
    destination = models.CharField(max_length=255, verbose_name='مقصد', null=True, blank=True)
    status = models.CharField(max_length=255, verbose_name='وضعیت', choices=STATUS_CHOICES, default='NOT_SENT_TO_BKI')
    
    # فیلد جدید برای ذخیره اطلاعات دریافتی از API بازارگاه
    bki_response_data = models.JSONField(verbose_name='اطلاعات دریافتی از بازارگاه', null=True, blank=True)
    # فیلد برای ذخیره شناسه حمل دریافتی از بازارگاه
    haml_id = models.CharField(max_length=255, verbose_name='شناسه حمل بازارگاه', null=True, blank=True)
    
    barnameh_date = jmodels.jDateField(verbose_name='تاریخ برنامه', null=True, blank=True)
    barnameh_updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    barnameh_created_at = jmodels.jDateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    is_sent_to_bki_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name='تاریخ ارسال به بازارگاه')

    is_created_by_excel = models.BooleanField(default=False, verbose_name='ایجاد توسط اکسل')
    is_sent_to_bki = models.BooleanField(default=False, verbose_name='ارسال به بازارگاه')
    
    # فیلدهای جدید برای مدیریت ستون‌ها
    buyer_postal_code = models.CharField(max_length=20, verbose_name='کدپستی خریدار', null=True, blank=True)
    transport_date = jmodels.jDateField(verbose_name='تاریخ حمل', null=True, blank=True)
    factor_sodoor_season = models.CharField(max_length=10, verbose_name='زمان صدور فاکتور فصل', null=True, blank=True)
    is_factored = models.BooleanField(default=False, verbose_name='فاکتور صادر شده')
    
    total_sales_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='مبلغ کل فروش', null=True, blank=True)
    total_purchase_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='مبلغ کل خرید', null=True, blank=True)

    # New field:
    factor_date = jmodels.jDateField(verbose_name='تاریخ ثبت فاکتور در سامانه مؤدیان', null=True, blank=True)

    class Meta:
        verbose_name = 'بارنامه'
        verbose_name_plural = 'بارنامه ها'

    def __str__(self):
        return f" {self.number} - {self.serial}"
    
    # متدهای کمکی برای دریافت اطلاعات از خرید مرتبط
    def get_cargo(self):
        """دریافت کوتاژ از خرید مرتبط"""
        return self.purchase.cargo if self.purchase else None
    
    def get_company_price(self):
        """دریافت فی خرید از خرید مرتبط"""
        try:
            return self.purchase.company_price if (self.purchase) else None
        except Exception as e:
            logger.error(f"خطا در دریافت فی خرید برای بارنامه {self.id}: {str(e)}")
            return None
    
    def get_customer_price(self):
        """دریافت فی فروش از خرید مرتبط"""
        try:
            return self.purchase.customer_price if (self.purchase) else None
        except Exception as e:
            logger.error(f"خطا در دریافت فی فروش برای بارنامه {self.id}: {str(e)}")
            return None
    
    def get_total_sales_amount(self):
        """دریافت مبلغ کل فروش"""
        # اگر مقدار ذخیره شده نباشد، محاسبه کن
        if self.purchase and self.purchase.customer_price and self.tonnage:
            return int(self.purchase.customer_price) * float(self.tonnage)
        return None  
    
    def get_total_purchase_amount(self):
        """دریافت مبلغ کل خرید"""
        # اگر مقدار ذخیره شده نباشد، محاسبه کن
        if self.purchase and self.purchase.company_price and self.tonnage:
            return int(self.purchase.company_price) * float(self.tonnage)
        return None
    
    def get_buyer_national_code(self):
        """دریافت شماره ملی خریدار از خرید مرتبط (buyer_national_id)"""
        return self.purchase.buyer_national_id if self.purchase else None

    def get_buyer_name(self):
        """دریافت نام خریدار از خرید مرتبط (buyer_name)"""
        return self.purchase.buyer_name if self.purchase else None

    def get_buyer_postal_code(self):
        """دریافت کدپستی تحویل گیرنده از خرید مرتبط (delivery_postal_code)"""
        if self.purchase and self.purchase.delivery_postal_code:
            return self.purchase.delivery_postal_code
        elif self.purchase and self.purchase.buyer_postal_code:
            return self.purchase.buyer_postal_code
        elif self.buyer_postal_code:
            return self.buyer_postal_code
        return None
    
    def get_buyer_name(self):
        """دریافت نام خریدار از خرید مرتبط"""
        return self.purchase.buyer_name if self.purchase else None
    
    def get_buyer_address(self):
        """دریافت آدرس خریدار از خرید مرتبط"""
        return self.purchase.address if self.purchase else None
    
    def get_demand_amount(self):
        """دریافت میزان تقاضا از خرید مرتبط"""
        return self.purchase.order_weight if self.purchase else None
    
    def get_importer(self):
        """دریافت واردکننده از کوتاژ"""
        return self.purchase.cargo.vared_konandeh if (self.purchase and self.purchase.cargo) else None
    
    def get_product_type(self):
        """دریافت نوع محصول از کوتاژ"""
        return self.purchase.cargo.get_product_type_display() if (self.purchase and self.purchase.cargo) else None
    
    def get_product_country(self):
        """دریافت کشور محصول از کوتاژ"""
        return self.purchase.cargo.get_country_display() if (self.purchase and self.purchase.cargo) else None
    
    def get_successful_send_date(self):
        """دریافت تاریخ ارسال موفق به بازارگاه"""
        return self.is_sent_to_bki_at
    
    def get_delivery_receiver_name(self):
        """دریافت نام تحویل گیرنده از شناسه تخصیص یا خرید مرتبط"""
        if self.shenase_takhsis and hasattr(self.shenase_takhsis, 'delivery_receiver_name') and self.shenase_takhsis.delivery_receiver_name:
            return self.shenase_takhsis.delivery_receiver_name
        elif self.purchase and self.purchase.delivery_receiver_name:
            return self.purchase.delivery_receiver_name
        elif self.purchase and self.purchase.buyer_name:
            return self.purchase.buyer_name
        elif self.receiver_name:
            return self.receiver_name
        return None
    
    def get_delivery_address(self):
        """دریافت آدرس تحویل از شناسه تخصیص یا خرید مرتبط"""
        if self.shenase_takhsis and hasattr(self.shenase_takhsis, 'delivery_address') and self.shenase_takhsis.delivery_address:
            return self.shenase_takhsis.delivery_address
        elif self.purchase and self.purchase.delivery_address:
            return self.purchase.delivery_address
        elif self.purchase and self.purchase.address:
            return self.purchase.address
        elif self.destination:
            return self.destination
        return None
    
    def set_the_purchase_and_shenase_takhsis(self):
        try:
            if self.shenase_takhsis_code:
                self.shenase_takhsis = ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code)
            if self.purchase_number:
                self.purchase = Purchase.objects.get(purchase_number=self.purchase_number)
        except Exception as e:
            logger.error(f"Error setting the purchase and shenase takhsis: {e}")
            

    def set_the_purchase_number_and_shenase_takhsis_code(self):
        try:
            if self.shenase_takhsis:
                self.shenase_takhsis_code=self.shenase_takhsis.code
            if self.purchase:
                self.purchase_number=self.purchase.purchase_number
        except Exception as e:
            logger.error(f"Error setting the purchase number and shenase takhsis code: {e}")


    def log_barnameh_edit(self, request):
        BarnamehLog.objects.create(barnameh=self, log_message=f"بارنامه توسط {request.user.username} ویرایش شد", log_date=timezone.now())
    
    # متد fill_the_purchase_number_if_we_got_shenase_takhsis حذف شد
    # کاربر باید خودش شناسه تخصیص صحیح را وارد کند

    def calculate_purchase_state_based_on_barnameh_weight(self, purchase):
        """
        محاسبه وضعیت جدید خرید بر اساس مجموع وزن بارنامه‌ها
        """
        if not purchase:
            return None
            
        # محاسبه مجموع وزن بارنامه‌های این خرید (شامل بارنامه فعلی)
        total_barnameh_weight = purchase.get_total_barnameh_weight()
        
        # اگر این بارنامه جدید است و هنوز در محاسبه قبلی لحاظ نشده، آن را اضافه کن
        if self.tonnage and self.pk:  # اگر بارنامه وزن دارد و ذخیره شده
            # بررسی اینکه آیا این بارنامه در محاسبه لحاظ شده یا نه
            existing_barnameh = purchase.barnamehs.filter(pk=self.pk).exists()
            if not existing_barnameh:
                total_barnameh_weight += float(self.tonnage or 0)
        elif self.tonnage and not self.pk:  # بارنامه جدید که هنوز ذخیره نشده
            total_barnameh_weight += float(self.tonnage or 0)
            
        order_weight = purchase.order_weight or 0
        
        # محاسبه اختلاف
        weight_difference = abs(order_weight - total_barnameh_weight)
        
        logger.info(f"🔍 محاسبه وضعیت خرید {purchase.id}: وزن سفارش={order_weight}, مجموع وزن بارنامه‌ها={total_barnameh_weight}, اختلاف={weight_difference}")
        
        # تعیین وضعیت جدید بر اساس اختلاف وزن
        if weight_difference < 5000:  # کمتر از 5000 کیلوگرم = بارنامه کامل
            new_state = 'BARNAMEH_ISSUED'
        else:  # بیشتر یا مساوی 5000 کیلوگرم = بارنامه ناقص
            new_state = 'BARNAMEH_INCOMPLETE'
            
        return new_state

    def update_purchase_state_if_needed(self, purchase, is_new_barnameh=False):
        """
        بروزرسانی وضعیت خرید در صورت نیاز
        """
        if not purchase:
            return False
            
        # بررسی اینکه آیا خرید در وضعیت قبل از بارنامه است یا نه
        pre_barnameh_states = [
            'INITIATED', 'SMS_SENT', 'PAYMENT_VERIFIED', 
            'ALLOCATION_APPROVED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH'
        ]
        
        current_state = purchase.state
        
        # اگر خرید در وضعیت قبل از بارنامه است یا در حالت بارنامه ناقص/کامل
        if current_state in pre_barnameh_states or current_state in ['BARNAMEH_INCOMPLETE', 'BARNAMEH_ISSUED']:
            new_state = self.calculate_purchase_state_based_on_barnameh_weight(purchase)
            
            if new_state and new_state != current_state:
                logger.info(f"✅ تغییر وضعیت خرید {purchase.id} از {current_state} به {new_state}")
                
                # بروزرسانی وضعیت خرید
                old_state = purchase.state
                purchase.state = new_state
                purchase.save(update_fields=['state'])
                
                # ایجاد رکورد تغییر وضعیت
                from core.PurchaseModel import PurchaseStateChange
                PurchaseStateChange.objects.create(
                    purchase=purchase,
                    previous_state=old_state,
                    new_state=new_state,
                    changed_by=None,  # تغییر توسط سیستم
                    notes=f"تغییر خودکار وضعیت بر اساس وزن بارنامه‌ها (اختلاف: {abs((purchase.order_weight or 0) - purchase.get_total_barnameh_weight())} کیلوگرم)"
                )
                
                logger.info(f"📝 رکورد تغییر وضعیت برای خرید {purchase.id} ایجاد شد")
                return True
            else:
                logger.info(f"⏭️ وضعیت خرید {purchase.id} تغییری نکرده ({current_state})")
        else:
            logger.info(f"⏭️ خرید {purchase.id} در وضعیت {current_state} است و نیاز به بروزرسانی ندارد")
            
        return False

    def save(self, *args, **kwargs):
        is_new = False if self.pk else True
        if not self.purchase or not self.shenase_takhsis:
            self.set_the_purchase_and_shenase_takhsis()
        if not self.purchase_number or not self.shenase_takhsis_code:
            self.set_the_purchase_number_and_shenase_takhsis_code()
        # حذف مکانیزم اتوماتیک تنظیم تخصیص - کاربر باید خودش تخصیص را وارد کند

        # همسان‌سازی کدپستی خریدار با خرید مرتبط
        if self.purchase and self.purchase.delivery_postal_code:
            self.buyer_postal_code = self.purchase.delivery_postal_code
        
        # تنظیم نام تحویل گیرنده و آدرس تحویل از شناسه تخصیص
        if self.shenase_takhsis:
            # تنظیم نام تحویل گیرنده از شناسه تخصیص
            if hasattr(self.shenase_takhsis, 'delivery_receiver_name') and self.shenase_takhsis.delivery_receiver_name:
                self.receiver_name = self.shenase_takhsis.delivery_receiver_name
            elif hasattr(self.shenase_takhsis, 'purchase') and self.shenase_takhsis.purchase and self.shenase_takhsis.purchase.buyer_name:
                self.receiver_name = self.shenase_takhsis.purchase.buyer_name
                
            # تنظیم آدرس تحویل از شناسه تخصیص
            if hasattr(self.shenase_takhsis, 'delivery_address') and self.shenase_takhsis.delivery_address:
                self.destination = self.shenase_takhsis.delivery_address
            elif hasattr(self.shenase_takhsis, 'purchase') and self.shenase_takhsis.purchase and self.shenase_takhsis.purchase.address:
                self.destination = self.shenase_takhsis.purchase.address

        # محاسبه فصل فاکتور بر اساس تاریخ ثبت فاکتور در سامانه مؤدیان
        if self.factor_date:
            # تبدیل تاریخ جلالی به فصل
            year = self.factor_date.year
            month = self.factor_date.month
            
            # تعیین فصل بر اساس ماه جلالی
            if month in [1, 2, 3]:  # فروردین، اردیبهشت، خرداد
                season = 1  # بهار
            elif month in [4, 5, 6]:  # تیر، مرداد، شهریور
                season = 2  # تابستان
            elif month in [7, 8, 9]:  # مهر، آبان، آذر
                season = 3  # پاییز
            else:  # دی، بهمن، اسفند
                season = 4  # زمستان
            
            # تولید کد فصل فاکتور (سال + فصل)
            self.factor_sodoor_season = f"{year}{season}"
            self.is_factored = True
        elif self.factor_sodoor_season is not None:
            self.is_factored = True
            
        if self.purchase and self.purchase.cargo and self.purchase.cargo.customer_price and self.tonnage:
            self.total_sales_amount = float(self.purchase.cargo.customer_price) * float(self.tonnage)
        if self.purchase and self.purchase.cargo and self.purchase.cargo.company_price and self.tonnage:
            self.total_purchase_amount = float(self.purchase.cargo.company_price) * float(self.tonnage)
    
        # بروزرسانی وضعیت بر اساس ارسال به بازارگاه
        if self.is_sent_to_bki:
            self.status = 'SENT_TO_BKI'
        else:
            self.status = 'NOT_SENT_TO_BKI'
        
        self.total_purchase_amount = self.get_total_purchase_amount()
        self.total_sales_amount = self.get_total_sales_amount()

        super().save(*args, **kwargs)
        
        # بروزرسانی وضعیت فاکتور خرید مرتبط
        if self.purchase:
            self.purchase.set_purchase_factor_status()
            
        # 🔄 بروزرسانی وضعیت خرید بر اساس وزن بارنامه‌ها
        # این کار را بعد از ذخیره انجام می‌دهیم تا بارنامه در دیتابیس موجود باشد
        # برای این کار از post_save signal استفاده می‌کنیم یا اینجا delay می‌کنیم
        
        # ابتدا اگر purchase مستقیماً موجود نیست، از طریق شناسه تخصیص پیدا کن
        purchase_to_update = self.purchase
        if not purchase_to_update and self.shenase_takhsis_code:
            try:
                from core.PurchaseModel import ShenaseTakhsis
                shenase_takhsis = ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code)
                purchase_to_update = shenase_takhsis.purchase
                logger.info(f"🔍 خرید {purchase_to_update.id if purchase_to_update else 'None'} از طریق شناسه تخصیص {self.shenase_takhsis_code} پیدا شد")
            except Exception as e:
                logger.warning(f"❌ خطا در پیدا کردن خرید از طریق شناسه تخصیص {self.shenase_takhsis_code}: {str(e)}")
                
        # 🔄 بروزرسانی وضعیت خرید بر اساس وزن بارنامه‌ها
        # این کار را در انتهای save انجام می‌دهیم تا مطمئن باشیم بارنامه کامل ذخیره شده
        purchase_to_update = self.purchase
        if not purchase_to_update and self.shenase_takhsis_code:
            try:
                shenase_takhsis = ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code)
                purchase_to_update = shenase_takhsis.purchase
                logger.info(f"🔍 خرید {purchase_to_update.id if purchase_to_update else 'None'} از طریق شناسه تخصیص {self.shenase_takhsis_code} پیدا شد")
            except Exception as e:
                logger.warning(f"❌ خطا در پیدا کردن خرید از طریق شناسه تخصیص {self.shenase_takhsis_code}: {str(e)}")
        
        # اگر هنوز خرید پیدا نشد و shenase_takhsis موجود است
        if not purchase_to_update and self.shenase_takhsis:
            purchase_to_update = self.shenase_takhsis.purchase
            logger.info(f"🔍 خرید {purchase_to_update.id if purchase_to_update else 'None'} از طریق شناسه تخصیص object پیدا شد")
                
        # بروزرسانی وضعیت خرید
        if purchase_to_update:
            self.update_purchase_state_if_needed(purchase_to_update, is_new_barnameh=is_new)
        else:
            logger.warning(f"⚠️ خرید مرتبط با بارنامه {self.id} پیدا نشد")


class BarnamehLog(models.Model):
    barnameh = models.ForeignKey(Barnameh, on_delete=models.CASCADE, related_name='barnameh_logs', verbose_name='بارنامه')
    log_date = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ')
    log_message = models.TextField(verbose_name='پیام')

    class Meta:
        verbose_name = 'لاگ بارنامه'
        verbose_name_plural = 'لاگ بارنامه ها'

    def __str__(self):
        return f"{self.barnameh.number} - {self.log_date}"


# @receiver(post_save, sender=Barnameh)
# def update_purchase_state_after_barnameh_save(sender, instance, created, **kwargs):
#     """
#     بروزرسانی وضعیت خرید بعد از ذخیره بارنامه
#     این signal غیرفعال شده و کار در متد save انجام می‌شود
#     """
#     pass

