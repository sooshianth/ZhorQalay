from django.db import models
from django_jalali.db import models as jmodels
from django.utils import timezone
from core.PurchaseModel import Purchase, ShenaseTakhsis
from major.models.NonBazargahPurchase import NonBazargahPurchase

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

    #فیلد های جدید
    # --------------------------------
    BARNAMEH_TYPE_CHOICES = [
        ('Bazargah', 'بازارگاهی'),
        ('Non_Bazargah', 'خارج بازارگاهی')
    ]

    origin = models.CharField(max_length=255, verbose_name='مبدا', null=True, blank=True)
    rent = models.PositiveBigIntegerField(verbose_name='کرایه', null=True, blank=True)
    type = models.CharField(max_length=20, verbose_name='نوع بارنامه', choices=BARNAMEH_TYPE_CHOICES, null=True, blank=True)
    non_bazargah_purchase = models.ForeignKey(NonBazargahPurchase, on_delete=models.CASCADE, verbose_name='خرید غیر بازارگاهی', null=True, blank=True)

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
            if self.purchase:
                return self.purchase.company_price
            elif self.non_bazargah_purchase and not self.purchase:
                return self.non_bazargah_purchase.company_price
            else:
                return None
            
        except Exception as e:
            logger.error(f"خطا در دریافت فی خرید برای بارنامه {self.id}: {str(e)}")
            return None
    
    def get_customer_price(self):
        """دریافت فی فروش از خرید مرتبط"""
        try:
            if self.purchase:
                return self.purchase.customer_price
            elif self.non_bazargah_purchase and not self.purchase:
                return self.non_bazargah_purchase.customer_price
            else:
                return None
            
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
        if self.purchase:
            return self.purchase.buyer_national_id
        elif self.non_bazargah_purchase and not self.purchase:
            return self.non_bazargah_purchase.buyer_national_id
        return None

    def get_buyer_name(self):
        """دریافت نام خریدار از خرید مرتبط (buyer_name)"""
        if self.purchase:
            return self.purchase.buyer_name
        elif self.non_bazargah_purchase and not self.purchase:
            return self.non_bazargah_purchase.buyer_name
        return None

    def get_buyer_postal_code(self):
        """دریافت کدپستی خریدار از خرید مرتبط (delivery_postal_code)"""
        if self.purchase:
            return self.purchase.buyer_postal_code
        elif self.non_bazargah_purchase and not self.purchase:
            return self.non_bazargah_purchase.buyer_postal_code
        return None
    
    def get_buyer_address(self):
        """دریافت آدرس خریدار از خرید مرتبط"""
        if self.purchase:
            return self.purchase.address
        elif self.non_bazargah_purchase and not self.purchase:
            return self.non_bazargah_purchase.address
        return None

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
    
    def get_non_product(self):
        return self.non_bazargah_purchase.product

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
    
    def fill_the_purchase_number_if_we_got_shenase_takhsis(self):
        try:
            if self.shenase_takhsis and not self.shenase_takhsis_code:
                self.shenase_takhsis_code=self.shenase_takhsis.code
            if self.shenase_takhsis_code and (not self.purchase_number or not self.purchase):
                self.shenase_takhsis_code=str(round(int(self.shenase_takhsis_code)))
                purchase=ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code).purchase
                self.purchase_number=purchase.purchase_number
                self.purchase=purchase
        except:
            logger.error('خطا در پر کردن شناسه خرید با اینکه شناسه تخصیص داریم')

    def save(self, *args, **kwargs):
        is_new = False if self.pk else True
        if not self.purchase or not self.shenase_takhsis:
            self.set_the_purchase_and_shenase_takhsis()
        if not self.purchase_number or not self.shenase_takhsis_code:
            self.set_the_purchase_number_and_shenase_takhsis_code()
        if (not self.purchase_number) and self.shenase_takhsis:
            self.fill_the_purchase_number_if_we_got_shenase_takhsis()
        if is_new:
            self.fill_the_purchase_number_if_we_got_shenase_takhsis()

        # همسان‌سازی کدپستی خریدار با خرید مرتبط
        if self.purchase and self.purchase.delivery_postal_code:
            self.buyer_postal_code = self.purchase.delivery_postal_code

        if self.factor_sodoor_season is not None:
            self.is_factored=True
            
        if self.purchase and self.purchase.cargo and self.purchase.cargo.customer_price and self.tonnage:
            self.total_sales_amount = float(self.purchase.cargo.customer_price) * float(self.tonnage)
        if self.purchase and self.purchase.cargo and self.purchase.cargo.company_price and self.tonnage:
            self.total_purchase_amount = float(self.purchase.cargo.company_price) * float(self.tonnage)
    
        # بروزرسانی وضعیت بر اساس ارسال به بازارگاه
        if self.is_sent_to_bki:
            self.status = 'SENT_TO_BKI'
        else:
            self.status = 'NOT_SENT_TO_BKI'

        if self.purchase and not self.non_bazargah_purchase:
            self.type = 'Bazargah'
        else:
            self.type = 'Non_Bazargah'

        self.total_purchase_amount = self.get_total_purchase_amount()
        self.total_sales_amount = self.get_total_sales_amount()

        super().save(*args, **kwargs)
        
        # بروزرسانی وضعیت فاکتور خرید مرتبط
        if self.purchase:
            self.purchase.set_purchase_factor_status()


class BarnamehLog(models.Model):
    barnameh = models.ForeignKey(Barnameh, on_delete=models.CASCADE, related_name='barnameh_logs', verbose_name='بارنامه')
    log_date = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ')
    log_message = models.TextField(verbose_name='پیام')

    class Meta:
        verbose_name = 'لاگ بارنامه'
        verbose_name_plural = 'لاگ بارنامه ها'

    def __str__(self):
        return f"{self.barnameh.number} - {self.log_date}"

