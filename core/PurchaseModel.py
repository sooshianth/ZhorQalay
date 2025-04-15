from django.db import models, transaction
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils import timezone
from .CustomerModel import Customer
from .CargoProductModel import CargoProduct
from .SalesAgentModel import SalesAgent
from django.contrib import messages
from sms_api.apis import (
    send_new_purchase_notification, 
    send_payment_confirmation, 
    send_address_notification, 
    send_barnameh_notification, 
    send_extelaf_notification
)

class Purchase(models.Model):
    id = models.AutoField(primary_key=True)
    invoice_id = models.CharField(max_length=20, unique=True, editable=False, blank=True, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name="مشتری", help_text="ارتباط یک‌به‌یک با مشتری از طریق شماره تلفن یا آیدی", related_name='purchases_made')
    address = models.TextField("آدرس", blank=True, null=True)
    description = models.TextField("توضیحات", blank=True, null=True)
    company_price = models.PositiveIntegerField("فی خرید(ریال)", default=0)
    customer_price = models.PositiveIntegerField("فی فروش(ریال)", default=0)

    purchase_number = models.CharField("شماره خرید بازارگاه", max_length=7, blank=True, null=True, unique=True)
    tracking_number = models.CharField("شماره پیگیری", max_length=6, blank=True, null=True, unique=True)
    shenase_takhsis = models.CharField("شناسه تخصیص", max_length=255, blank=True, null=True, unique=False)
    code_melli_tahvil = models.CharField("کد ملی تحویل", max_length=255, blank=True, null=True, unique=True)
    bazaargah_phone_number = models.CharField("شماره تلفن بازارگاه", max_length=11, blank=True, null=True)
    tahvil_phone_number = models.CharField("شماره تلفن تحویل", max_length=11, blank=True, null=True)

    weight = models.PositiveIntegerField("وزن (کیلوگرم)", default=0)
    cargo = models.ForeignKey(CargoProduct,on_delete=models.SET_NULL, verbose_name="کوتاژ", null=True, blank=True, related_name='purchases')
    type = models.CharField("نوع خرید", max_length=25, default='bazaargah')
    amount_paid = models.PositiveBigIntegerField("مبلغ پرداختی(ریال)", blank=True, null=True)
    payment_method = models.CharField("شیوۀ پرداخت", max_length=6, choices=[('نقدی', 'نقدی'), ('توافقی', 'توافقی')], default="نقدی")
    created_at = jmodels.jDateTimeField("تاریخ ثبت", default=timezone.now)
    updated_at  = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True, blank=True, null=True)
    is_weight_costed = models.BooleanField("آیا وزن خرید از وزن موجود محصول کاسته شده است؟", default=False)
    is_ap_af = models.BooleanField("آیا مبلغ خرید اتوکامپلیت شده است؟", default=False)
    extelaf_type = models.CharField("نوع اختلاف (کسری یا سرک)", max_length=4, choices=[('کسری', 'کسری'), ('سرک', 'سرک')], null=True, blank=True)
    extelaf_weight = models.PositiveIntegerField("وزن اختلاف به کیلوگرم", null=True, blank=True)
    extelaf_amount = models.PositiveBigIntegerField("مبلغ اختلاف به ریال", null=True, blank=True)

    #################################################
    ##           BOOOOLLLEAAANNNNSSSSSSSSSS        ##
    #################################################
    is_sms_sent = models.BooleanField("پیامک ارسال شده", default=True)
    is_bazaargahed = models.BooleanField("تایید بازارگاه ", default=False)
    is_paid = models.BooleanField("تایید مالی", default=False)
    is_takhsised = models.BooleanField("تخصیص شده", default=False)
    is_takhsised_approved = models.BooleanField("تایید تخصیص", default=False)
    is_tasvied_with_varedkonandeh = models.BooleanField("تسویه با واردکننده", default=False)

    is_address_sent_to_varedkonandeh = models.BooleanField("ارسال آدرس به واردکننده", default=False)
    is_sent_to_barbari = models.BooleanField("ارسال به باربری", default=False)
    is_barnamed = models.BooleanField("ارسال شده", default=False)
    is_ekhtelaf_approved = models.BooleanField("تایید مبلغ اختلاف", default=False)

    is_kasri_varized = models.BooleanField("واریز کسری", default=False)
    is_sarak_varized = models.BooleanField("واریز سرک", default=False)
    is_kasri_reciept_submited = models.BooleanField("ثبت رسید کسری", default=False)

    is_factorated = models.BooleanField("صدور فاکتور", default=False)

    does_salesman_approve = models.BooleanField("تایید واحد فروش", default=False)
    does_logistics_approve = models.BooleanField("تایید واحد لجستیک", default=False)
    does_financial_approve = models.BooleanField("تایید واحد مالی", default=False)


    is_urgent = models.BooleanField("پیگیری فوری", default=False)
    is_canceled = models.BooleanField("لغو شده", default=False)
    is_archived = models.BooleanField("آرشیو شده", default=False)
    
    ################################################################3

    is_sent = models.BooleanField("ارسال شده", default=False)
    is_delivered = models.BooleanField("تحویل داده شده", default=False)




    def check_is_bazaaragahed(self, user_role):
        if self.type == 'bazaargah':
            if self.purchase_number:
                if user_role == 'logistics_manager':
                    self.is_bazaargahed = True
                else:
                    raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            else:
                raise ValidationError('شماره خرید الزامی است')
        else:
            raise ValidationError('این خرید خارج از بازارگاه است')
                
    def check_is_paid(self, user_role):
        if self.type == 'bazaargah':
            if user_role == 'financial_manager' and self.is_bazaargahed and (type(self.amount_paid) == int and self.amount_paid > 10000000):
                self.is_paid = True
                if not self.is_weight_costed:
                    self.is_weight_costed = True
                    self.cargo.weight -= self.weight
                    self.cargo.save()
                # Send SMS notification for payment confirmation
                send_payment_confirmation(self)
            else:
                raise ValidationError('مبلغ هنوز وارد نشده است')
        else:
            if user_role == 'financial_manager' and (type(self.amount_paid) == int and self.amount_paid > 10000000):
                self.is_paid = True
                if not self.is_weight_costed:
                    self.is_weight_costed = True
                    self.cargo.weight -= self.weight
                    self.cargo.save()
                # Send SMS notification for payment confirmation
                send_payment_confirmation(self)
            else:
                raise ValidationError('مبلغ هنوز وارد نشده است')
        
    def check_is_takhsised(self, user_role):
        if user_role == 'sales_agent':
            self.is_takhsised = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
        
    def check_is_takhsised_approved(self, user_role):
        if user_role == 'logistics_manager':
            self.is_takhsised_approved = True
            self.is_takhsised = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')

    def check_is_tasvied_with_varedkonandeh(self, user_role):
        if user_role == 'financial_manager' and self.is_paid:
            self.is_tasvied_with_varedkonandeh = True
        else:
            raise ValidationError('این خرید هنوز پرداخت نشده است')
    
    def check_is_address_sent_to_varedkonandeh(self, user_role):
        if user_role == 'logistics_manager' and self.is_tasvied_with_varedkonandeh:
            self.is_address_sent_to_varedkonandeh = True
            # Send SMS notification for address sent to importer
            send_address_notification(self)
        else:
            raise ValidationError('این خرید هنوز با واردکننده تسویه نشده است')

    def check_is_sent_to_barbari(self, user_role):
        if user_role == 'logistics_manager' and self.is_address_sent_to_varedkonandeh:
            self.is_sent_to_barbari = True
        else:
            raise ValidationError('آدرس این خرید هنوز ارسال نشده است')
        
    def check_is_barnamed(self, user_role):
        if user_role == 'logistics_manager' and self.barnameh:
            self.is_barnamed = True
            self.is_sent = True
            # Send SMS notification for barnameh (shipping info)
            send_barnameh_notification(self)
        else:
            raise ValidationError('شماره بارنامه این خرید هنوز ثبت نشده است')
        
    def check_is_ekhtelaf_approved(self, user_role):
        if user_role == 'financial_manager' and self.is_barnamed:
            self.is_ekhtelaf_approved = True
            self.is_delivered = True
            # If there's a weight difference (extelaf) of type "sarak", send notification
            if self.extelaf_type == 'سرک' and self.extelaf_weight and self.extelaf_amount:
                send_extelaf_notification(self)
        else:
            raise ValidationError('بار هنوز به مشتری تحویل داده نشده است')
        
    def check_is_kasri_varized(self, user_role):
        if user_role == 'financial_manager' and self.is_ekhtelaf_approved:
            self.is_kasri_varized = True
        else:
            raise ValidationError('مبلغ و مقدار اختلاف در سیستم ثبت نشده است')
    
    def check_is_sarak_varized(self, user_role):
        if user_role == 'sales_agent' and self.is_ekhtelaf_approved:
            self.is_sarak_varized = True
        else:
            raise ValidationError('مبلغ و مقدار اختلاف در سیستم ثبت نشده است')
        
    def check_is_kasri_reciept_submited(self, user_role):
        if user_role == 'financial_manager' and (self.is_kasri_varized or self.is_sarak_varized):
            self.is_kasri_reciept_submited = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')

    def check_is_factorated(self, user_role):
        if user_role == 'financial_manager' and self.is_kasri_reciept_submited:
            self.is_factorated = True
        else:
            raise ValidationError('تایید اختلاف هنوز انجام نشده است')


    def check_does_salesman_approve(self, user_role):
        if user_role == 'sales_agent' and self.is_kasri_reciept_submited:
            self.does_salesman_approve = True
    def check_does_logistics_approve(self, user_role):
        if user_role == 'logistics_manager' and self.is_kasri_reciept_submited:
            self.does_logistics_approve = True
    def check_does_financial_approve(self, user_role):
        if user_role == 'financial_manager' and self.is_factorated:
            self.does_financial_approve = True


    def check_is_urgent(self, user):
        if user.is_superuser:
            self.is_urgent = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')

    def check_is_canceled(self, user):
        if user.is_superuser:
            self.is_canceled = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')

    def check_is_archived(self, user):
        if user.is_superuser:
            self.is_archived = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    class Meta:
        verbose_name = "خرید"
        verbose_name_plural = "خریدها"
    
    def __str__(self):
        return f"خرید {self.purchase_number} - {self.customer.name} در تاریخ {self.created_at}"

    def clean(self):
        errors = {}
        if self.purchase_number:
            if len(str(self.purchase_number)) != 7 or not self.purchase_number.isdigit():
                errors['purchase_number'] = 'شماره خرید باید دقیقاً 7 رقم عددی باشد'

        if self.tracking_number:
            if len(str(self.tracking_number)) != 6 or not self.tracking_number.isdigit():
                errors['tracking_number'] = 'شماره پیگیری باید دقیقاً 6 رقم عددی باشد'
        
        if len(str(self.amount_paid)) > 12 and len(str(self.amount_paid)) < 7:
            errors['amount_paid'] = 'مبلغ پرداختی باید بین 7 و 11 رقم باشد'
        if self.is_paid and not self.amount_paid:
            errors['amount_paid'] = 'برای خریدهای پرداخت شده مبلغ الزامی است'
        elif self.is_paid and self.amount_paid <= 100000000:
            errors['amount_paid'] = 'مبلغ پرداختی باید بزرگتر از صد میلیون تومان باشد'

        if self.weight <= 10000:
            errors['weight'] = 'وزن باید بزرگتر از 10 تن باشد'
        
        if not self.customer:
            errors['customer'] = 'انتخاب مشتری الزامی است'
        
        if self.is_archived:
            if self.is_paid or self.is_sent or self.is_delivered or self.is_canceled:
                errors['is_archived'] = 'خرید آرشیو شده نمی‌تواند پرداخت شده، ارسال شده، تحویل داده شده یا لغو شده باشد.'
        if self.customer_price != 0 and (self.customer_price < 50000 or self.customer_price > 300000):
            raise ValidationError('فی فروش عددی غیرواقعی است.')
        if self.company_price != 0 and (self.company_price < 50000 or self.company_price > 300000):
            raise ValidationError('فی خرید عددی غیرواقعی است.')

        if errors:
            raise ValidationError(errors)
            
    def save(self, *args, **kwargs):
        is_new = not self.pk  # Check if this is a new instance
        
        if not self.invoice_id:
            if len(self.customer.sales_agent.all()) > 1:
                factor_code = '88'
            else:
                for sales_agent in SalesAgent.objects.all():
                    if sales_agent in self.customer.sales_agent.all():
                        factor_code = sales_agent.factor_code
            last_purchase = Purchase.objects.filter(invoice_id__startswith=factor_code).order_by('-invoice_id').first()
            if last_purchase:
                last_serial = str(last_purchase.invoice_id)[2:]
                new_serial = int(last_serial) + 1
            else:
                new_serial = 1
            self.invoice_id = f"{factor_code}{str(new_serial).zfill(4)}"

        if self.cargo:
            self.type = self.cargo.type
            if self.customer_price == 0:
                self.price = self.cargo.customer_price
            if self.company_price == 0:
                self.company_price = self.cargo.company_price
                
        super().save(*args, **kwargs)
        
        # Send SMS notification for new purchase only on creation
        if is_new and self.customer.sms_preference:
            send_new_purchase_notification(self)

from django.contrib.auth.models import User
class PurchaseHistory(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changes = models.TextField("تغییرات")
    timestamp = jmodels.jDateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تاریخچه خرید"
        verbose_name_plural = "تاریخچه خریدها"

    def __str__(self):
        return f"{self.timestamp} - {self.user}"

class ShenaseTakhsis(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='shenase_takhsis_set', verbose_name="خرید مرتبط")
    code = models.CharField("شناسه تخصیص", max_length=255, unique=True)
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)
    
    class Meta:
        verbose_name = "شناسه تخصیص"
        verbose_name_plural = "شناسه‌های تخصیص"
        unique_together = ['purchase', 'code']
    
    def __str__(self):
        return f"شناسه تخصیص {self.code} برای خرید {self.purchase.id}"

