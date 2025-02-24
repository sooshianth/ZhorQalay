from django.db import models
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import Customer, CargoProduct
from .extensions import utils

class Purchase(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name="مشتری", help_text="ارتباط یک‌به‌یک با مشتری از طریق شماره تلفن یا آیدی", related_name='purchases_made')
    address = models.TextField("آدرس", blank=True, null=True)
    purchase_number = models.CharField("شماره خرید", max_length=255, blank=True, null=True)
    tracking_number = models.CharField("شماره پیگیری", max_length=255, blank=True, null=True)
    weight = models.PositiveIntegerField("وزن (کیلوگرم)")
    cargo = models.ForeignKey(CargoProduct,on_delete=models.SET_NULL, verbose_name="کوتاژ", blank=True, null=True)
    amount_paid = models.PositiveBigIntegerField("مبلغ پرداختی(ریال)", blank=True, null=True)
    created_at = models.DateTimeField("تاریخ ثبت",default=timezone.now,editable=True)
    updated_at  = models.DateTimeField("تاریخ بروزرسانی",auto_now=True)
    is_paid = models.BooleanField("پرداخت شده", default=False)
    is_takhsised = models.BooleanField("تخصیص شده", default=False)
    is_sent_to_barbari = models.BooleanField("ارسال به باربری", default=False)
    is_sent = models.BooleanField("ارسال شده", default=False)
    is_delivered = models.BooleanField("تحویل داده شده", default=False)
    is_canceled = models.BooleanField("لغو شده", default=False)
    is_archived = models.BooleanField("آرشیو شده", default=False)

    class Meta:
        verbose_name = "خرید"
        verbose_name_plural = "خریدها"
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.is_paid and self.cargo:
            self.cargo.weight -= self.weight
            self.cargo.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"خرید {self.purchase_number} - {self.customer.name} در تاریخ {self.created_at}"


    def return_created_at(self):
        return utils.time_convertor(self.created_at)
    def return_updated_at(self):
        return utils.time_convertor(self.updated_at)
    
    def change_is_paid(self):
        temp = self.is_paid
        self.is_paid = not temp
    def change_is_sent(self):
        temp = self.is_sent
        self.is_sent = not temp
    def change_is_delivered(self):
        temp = self.is_delivered
        self.is_delivered = not temp
    def change_is_canceled(self):
        temp = self.is_canceled
        self.is_canceled = not temp
    def change_is_archived(self):
        temp = self.is_archived
        self.is_archived = not temp

    def clean(self):
        errors = {}
        if self.purchase_number:
            if len(str(self.purchase_number)) != 7 or not self.purchase_number.isdigit():
                errors['purchase_number'] = 'شماره خرید باید دقیقاً 7 رقم عددی باشد'

        if self.tracking_number:
            if len(str(self.tracking_number)) != 6 or not self.tracking_number.isdigit():
                errors['tracking_number'] = 'شماره پیگیری باید دقیقاً 6 رقم عددی باشد'
        
        if len(str(self.amount_paid)) > 11 and len(self.amount_paid) < 7:
            errors['amount_paid'] = 'مبلغ پرداختی باید بین 7 و 11 رقم باشد'
        if self.is_paid and not self.amount_paid:
            errors['amount_paid'] = 'برای خریدهای پرداخت شده مبلغ الزامی است'
        elif self.is_paid and self.amount_paid <= 100000000:
            errors['amount_paid'] = 'مبلغ پرداختی باید بزرگتر از صد میلیون تومان باشد'

        if self.weight <= 10000:
            errors['weight'] = 'وزن باید بزرگتر از 10 تن باشد'

        if self.is_delivered and not self.is_sent:
            errors['is_delivered'] = 'کالای تحویل شده باید ابتدا ارسال شده باشد'
        
        if self.is_canceled and self.is_delivered:
            errors['is_canceled'] = 'کالای تحویل شده قابل لغو نیست'

        if not self.customer:
            errors['customer'] = 'انتخاب مشتری الزامی است'
        
        if self.is_archived:
            if self.is_paid or self.is_sent or self.is_delivered or self.is_canceled:
                errors['is_archived'] = 'خرید آرشیو شده نمی‌تواند پرداخت شده، ارسال شده، تحویل داده شده یا لغو شده باشد.'

        if errors:
            raise ValidationError(errors)



from django.contrib.auth.models import User

class PurchaseHistory(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changes = models.TextField("تغییرات")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تاریخچه خرید"
        verbose_name_plural = "تاریخچه خریدها"

    def __str__(self):
        return f"{self.timestamp} - {self.user}"