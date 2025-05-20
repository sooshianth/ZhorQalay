from django.db import models
from django_jalali.db import models as jmodels
from django.utils import timezone
from core.PurchaseModel import Purchase, ShenaseTakhsis

class Barnameh(models.Model):
    STATUS_CHOICES = [
        ('BARNAMEH_INCOMPLETE', 'بارنامه ناقص'),
        ('BARNAMEH_COMPLETE', 'بارنامه کامل'),
        ('PURCHASE_CLOSED', 'بستن خرید در بازارگاه'),
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
    status = models.CharField(max_length=255, verbose_name='وضعیت', choices=STATUS_CHOICES, default='BARNAMEH_INCOMPLETE')
    
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

    class Meta:
        verbose_name = 'بارنامه'
        verbose_name_plural = 'بارنامه ها'

    def __str__(self):
        return f" {self.number} - {self.serial}"
    
    def set_the_purchase_and_shenase_takhsis(self):
        try:
            if self.shenase_takhsis_code:
                self.shenase_takhsis = ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code)
            if self.purchase_number:
                self.purchase = Purchase.objects.get(purchase_number=self.purchase_number)
        except Exception as e:
            print(f"Error setting the purchase and shenase takhsis: {e}")
            

    def set_the_purchase_number_and_shenase_takhsis_code(self):
        try:
            if self.shenase_takhsis:
                self.shenase_takhsis_code=self.shenase_takhsis.code
            if self.purchase:
                self.purchase_number=self.purchase.purchase_number
        except Exception as e:
            print(f"Error setting the purchase number and shenase takhsis code: {e}")


    def log_barnameh_edit(self, request):
        BarnamehLog.objects.create(barnameh=self, log_message=f"بارنامه توسط {request.user.username} ویرایش شد", log_date=timezone.now())
    
    def fill_the_purchase_number_if_we_got_shenase_takhsis(self):
        try:
            if self.shenase_takhsis:
                self.shenase_takhsis_code=self.shenase_takhsis.code
            if self.shenase_takhsis_code:
                self.shenase_takhsis_code=str(round(int(self.shenase_takhsis_code)))
                purchase=ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code).purchase
                self.purchase_number=purchase.purchase_number
                self.purchase=purchase
        except:
            print('خطا در پر کردن شناسه خرید با اینکه شناسه تخصیص داریم')

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
        if self.purchase:
            if self.purchase.status in ['INITIATED', 'SMS_SENT', 'PAYMENT_VERIFIED', 'ALLOCATION_APPROVED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH']:
                self.status = 'BARNAMEH_INCOMPLETE'
        super().save(*args, **kwargs)


class BarnamehLog(models.Model):
    barnameh = models.ForeignKey(Barnameh, on_delete=models.CASCADE, related_name='barnameh_logs', verbose_name='بارنامه')
    log_date = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ')
    log_message = models.TextField(verbose_name='پیام')

    class Meta:
        verbose_name = 'لاگ بارنامه'
        verbose_name_plural = 'لاگ بارنامه ها'

    def __str__(self):
        return f"{self.barnameh.number} - {self.log_date}"

