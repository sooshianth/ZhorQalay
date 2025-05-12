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
        self.purchase = Purchase.objects.get(purchase_number=self.purchase_number)
        self.shenase_takhsis = ShenaseTakhsis.objects.get(code=self.shenase_takhsis_code)

    def save(self, *args, **kwargs):
        if not self.purchase or not self.shenase_takhsis:
            self.set_the_purchase_and_shenase_takhsis()
        super().save(*args, **kwargs)
