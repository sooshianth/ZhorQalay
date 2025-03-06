from django.db import models, transaction
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils import timezone
from .CustomerModel import Customer
from .CargoProductModel import CargoProduct

class Purchase(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, verbose_name="مشتری", help_text="ارتباط یک‌به‌یک با مشتری از طریق شماره تلفن یا آیدی", related_name='purchases_made')
    address = models.TextField("آدرس", blank=True, null=True)
    purchase_number = models.CharField("شماره خرید بازارگاه", max_length=255, blank=True, null=True, unique=True)
    tracking_number = models.CharField("شماره پیگیری", max_length=255, blank=True, null=True, unique=True)
    weight = models.PositiveIntegerField("وزن (کیلوگرم)",)
    cargo = models.ForeignKey(CargoProduct,on_delete=models.SET_NULL, verbose_name="کوتاژ", blank=True, null=True)
    amount_paid = models.PositiveBigIntegerField("مبلغ پرداختی(ریال)", blank=True, null=True)
    payment_method = models.CharField("شیوۀ پرداخت", max_length=6, choices=[('نقدی', 'نقدی'), ('توافقی', 'توافقی')], default="نقدی")
    created_at = jmodels.jDateTimeField("تاریخ ثبت",default=timezone.now,editable=True)
    updated_at  = jmodels.jDateTimeField("تاریخ بروزرسانی",auto_now=True)
    is_weight_costed = models.BooleanField("آیا وزن خرید از وزن موجود محصول کاسته شده است؟", default=False)

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
    is_factorated = models.BooleanField("صدور فاکتور", default=False)
    is_ekhtelaf_approved = models.BooleanField("تایید مبلغ اختلاف", default=False)

    is_kasri_varized = models.BooleanField("واریز کسری", default=False)
    is_sarak_varized = models.BooleanField("واریز سرک", default=False)
    is_kasri_reciept_submited = models.BooleanField("ثبت رسید کسری", default=False)

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
        if user_role == 'logistics_manager':
            self.is_bazaargahed = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    def check_is_paid(self, user_role):
        if user_role == 'financial_manager' and self.is_bazaargahed and (type(self.amount_paid) == int and self.amount_paid > 10000000):
            self.is_paid = True
            if not self.is_weight_costed:
                self.is_weight_costed = True
                self.cargo.weight -= self.weight
                self.cargo.save()
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    def check_is_takhsised(self, user_role):
        if user_role == 'sales_agent':
            self.is_takhsised = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
        
    def check_is_takhsised_approved(self, user_role):
        if user_role == 'logistics_manager' and self.is_takhsised:
            self.is_takhsised_approved = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')

    def check_is_tasvied_with_varedkonandeh(self, user_role):
        if user_role == 'financial_manager':
            self.is_tasvied_with_varedkonandeh = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
    
    def check_is_address_sent_to_varedkonandeh(self, user_role):
        if user_role == 'logistics_manager' and self.is_tasvied_with_varedkonandeh:
            self.is_address_sent_to_varedkonandeh = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')

    def check_is_sent_to_barbari(self, user_role):
        if user_role == 'logistics_manager' and self.is_address_sent_to_varedkonandeh:
            self.is_sent_to_barbari = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    def check_is_barnamed(self, user_role):
        if user_role == 'logistics_manager':
            self.is_barnamed = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    def check_is_factorated(self, user_role):
        if user_role == 'financial_manager' and self.is_barnamed:
            self.is_factorated = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
    
    def check_is_ekhtelaf_approved(self, user_role):
        if user_role == 'financial_manager' and self.is_factorated:
            self.is_ekhtelaf_approved = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    def check_is_kasri_varized(self, user_role):
        if user_role == 'financial_manager' and self.is_ekhtelaf_approved:
            self.is_kasri_varized = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
    
    def check_is_sarak_varized(self, user_role):
        if user_role == 'sales_agent' and self.is_kasri_varized:
            self.is_sarak_varized = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
    def check_is_kasri_reciept_submited(self, user_role):
        if user_role == 'financial_manager':
            self.is_kasri_reciept_submited = True
        else:
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')


    def check_does_salesman_approve(self, user_role):
        if user_role == 'sales_agent' and self.is_kasri_reciept_submited:
            self.does_salesman_approve = True
    def check_does_logistics_approve(self, user_role):
        if user_role == 'logistics_manager' and self.is_kasri_reciept_submited:
            self.does_logistics_approve = True
    def check_does_financial_approve(self, user_role):
        if user_role == 'financial_manager' and self.is_kasri_reciept_submited:
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

        if errors:
            raise ValidationError(errors)




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

