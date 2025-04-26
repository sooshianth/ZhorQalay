from django.db import models, transaction
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils import timezone
from .CustomerModel import Customer
from .CargoProductModel import CargoProduct
from .SalesAgentModel import SalesAgent
from django.contrib import messages
from django.contrib.auth.models import User

# حذف ایمپورت مستقیم sms_api برای جلوگیری از ایمپورت دایره‌ای
# from sms_api.apis import (
#     send_new_purchase_notification, 
#     send_payment_confirmation, 
#     send_address_notification, 
#     send_barnameh_notification, 
#     send_extelaf_notification
# )

# تابع کمکی برای ایمپورت با تاخیر توابع sms
def get_sms_api():
    from sms_api import apis
    return apis

def determine_user_role(user):
    """
    تشخیص نقش کاربر براساس روابط او
    به جای بررسی مستقیم role که وجود ندارد، روابط بررسی می‌شود
    نقش لجستیک بر فروش ارجحیت دارد
    """
    if hasattr(user, 'financial_manager') and user.financial_manager is not None:
        return 'financial_manager'
    elif hasattr(user, 'logistics_manager') and user.logistics_manager is not None:
        return 'logistics_manager'
    elif hasattr(user, 'sales_agent') and user.sales_agent is not None:
        return 'sales_agent'
    elif hasattr(user, 'support_agent') and user.support_agent is not None:
        return 'support_agent'
    elif user.is_superuser:
        # مدیر ارشد دسترسی کامل دارد
        return 'admin'
    return None

class Purchase(models.Model):
    # وضعیت‌های مختلف خرید
    STATUS_CHOICES = [
        ('INITIATED', 'شروع شده'), # system
        ('SMS_SENT', 'پیامک ارسال شده'), # system
        ('BAZAARGAH_CONFIRMED', 'تایید بازارگاه'), # logistics_manager
        ('ALLOCATION_REGISTERED', 'ثبت تخصیص'), # sales_agent
        ('ALLOCATION_APPROVED', 'تایید تخصیص'),  # logistics_manager
        ('PAYMENT_VERIFIED', 'تایید مالی'),  # financial_manager
        ('VENDOR_SETTLED', 'تسویه با واردکننده'),  # financial_manager
        ('ADDRESS_SENT', 'ارسال آدرس به واردکننده'), # logistics_manager
        ('SENT_TO_SHIPPING', 'ارسال به باربری'), # logistics_manager
        ('BARNAMEH_ISSUED', 'بارنامه صادر شده'), # logistics_manager
        ('DELIVERED', 'تحویل به مشتری'), # logistics_manager
        ('DIFFERENCE_APPROVED', 'تایید مقدار و مبلغ اختلاف'), # financial_manager
        ('DIFFERENCE_DEPOSITED', 'ثبت واریز اختلاف'), # sales_agent financial_manager 
        ('RECEIPT_SUBMITTED', 'ثبت رسید واریزی اختلاف'), # financial_manager
        ('INVOICE_ISSUED', 'صدور فاکتور'), # financial_manager
        ('SALES_APPROVED', 'تایید واحد فروش'), # sales_agent
        ('LOGISTICS_APPROVED', 'تایید واحد لجستیک'), # logistics_manager
        ('FINANCIAL_APPROVED', 'تایید واحد مالی'), # financial_manager
        ('COMPLETED', 'تکمیل شده'), # system
        ('URGENT', 'پیگیری فوری'), # admin
        ('CANCELED', 'لغو شده'), # admin
        ('ARCHIVED', 'آرشیو شده'), # admin
    ]
    
    id = models.AutoField(primary_key=True)
    state = models.CharField("وضعیت", max_length=50, choices=STATUS_CHOICES, default='INITIATED')
    invoice_id = models.CharField(max_length=20, verbose_name='کد درون سازمانی', unique=True, editable=False, blank=True, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="مشتری", help_text="ارتباط یک‌به‌یک با مشتری از طریق شماره تلفن یا آیدی", related_name='purchases_made')
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
    barnameh = models.CharField("شماره بارنامه", max_length=255, blank=True, null=True)
    
    send_cottage_sms = models.BooleanField('ارسال پیامک کوتاژ', default=True)
    order_weight = models.PositiveIntegerField("وزن سفارش (کیلوگرم)", default=0)
    delivered_weight = models.PositiveIntegerField("وزن تحویلی (کیلوگرم)", default=0)
    cargo = models.ForeignKey(CargoProduct,on_delete=models.SET_NULL, verbose_name="کوتاژ", null=True, blank=True, related_name='purchases')
    type = models.CharField("نوع خرید", max_length=25, default='bazaargah', choices=[('bazaargah', 'بازارگاه'), ('non_bazaargah', 'خارج از بازارگاه')])
    amount_paid = models.PositiveBigIntegerField("مبلغ پرداختی(ریال)", blank=True, null=True)
    payment_method = models.CharField("شیوۀ پرداخت", max_length=6, choices=[('نقدی', 'نقدی'), ('توافقی', 'توافقی')], default="نقدی")
    created_at = jmodels.jDateTimeField("تاریخ ثبت", default=timezone.now)
    updated_at  = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True, blank=True, null=True)
    is_weight_costed = models.BooleanField("آیا وزن خرید از وزن موجود محصول کاسته شده است؟", default=False)
    is_ap_af = models.BooleanField("آیا مبلغ خرید اتوکامپلیت شده است؟", default=False)
    extelaf_type = models.CharField("نوع اختلاف (کسری یا سرک)", max_length=4, choices=[('کسری', 'کسری'), ('سرک', 'سرک')], null=True, blank=True)
    extelaf_weight = models.PositiveIntegerField("وزن اختلاف به کیلوگرم", null=True, blank=True)
    extelaf_amount = models.PositiveBigIntegerField("مبلغ اختلاف به ریال", null=True, blank=True)
    
    is_urgent = models.BooleanField("آیا خرید فوری است؟", default=False)
    is_canceled = models.BooleanField("آیا خرید لغو شده است؟", default=False)
    is_archived = models.BooleanField("آیا خرید آرشیو شده است؟", default=False)
    def change_state(self, new_state, user, notes=None):
        """
        متد عمومی برای تغییر وضعیت خرید و ثبت آن در تاریخچه
        """
        old_state = self.state
        self.state = new_state
        self.save()
        
        # ثبت تغییر وضعیت در تاریخچه
        PurchaseStateChange.objects.create(
            purchase=self,
            previous_state=old_state,
            new_state=new_state,
            changed_by=user,
            notes=notes
        )
        return True

    def confirm_bazaargah(self, user):
        """
        تایید خرید در بازارگاه
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.type != 'bazaargah':
            raise ValidationError('این خرید خارج از بازارگاه است')
            
        if not self.purchase_number:
            raise ValidationError('شماره خرید الزامی است')
        
        return self.change_state('BAZAARGAH_CONFIRMED', user, 'تایید شده در بازارگاه')
        
    def verify_payment(self, user):
        """
        تایید پرداخت
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.type == 'bazaargah' and self.state != 'BAZAARGAH_CONFIRMED':
            raise ValidationError('ابتدا باید خرید در بازارگاه تایید شود')
            
        if not self.amount_paid or self.amount_paid <= 10000000:
            raise ValidationError('مبلغ پرداختی باید بزرگتر از 10 میلیون ریال باشد')
            
        # کسر از موجودی محصول
        if not self.is_weight_costed and self.cargo:
            self.is_weight_costed = True
            self.cargo.weight -= self.order_weight
            self.cargo.save()
            
        # ارسال پیامک تایید پرداخت با استفاده از ایمپورت تاخیری
        sms_api = get_sms_api()
        sms_api.send_payment_confirmation(self)
        
        return self.change_state('PAYMENT_VERIFIED', user, 'تایید مالی انجام شد')
        
    def register_allocation(self, user):
        """
        ثبت تخصیص
        """
        user_role = determine_user_role(user)
        if user_role != 'sales_agent' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if not self.shenase_takhsis:
            raise ValidationError('شناسه تخصیص الزامی است')
        
        return self.change_state('ALLOCATION_REGISTERED', user, 'تخصیص ثبت شد')
        
    def approve_allocation(self, user):
        """
        تایید تخصیص
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'ALLOCATION_REGISTERED':
            raise ValidationError('ابتدا باید تخصیص ثبت شود')
        
        return self.change_state('ALLOCATION_APPROVED', user, 'تخصیص تایید شد')
        
    def settle_with_vendor(self, user):
        """
        تسویه با واردکننده
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'PAYMENT_VERIFIED' and self.state != 'ALLOCATION_APPROVED':
            raise ValidationError('ابتدا باید پرداخت تایید شود')
        
        return self.change_state('VENDOR_SETTLED', user, 'تسویه با واردکننده انجام شد')
        
    def send_address_to_vendor(self, user):
        """
        ارسال آدرس به واردکننده
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'VENDOR_SETTLED':
            raise ValidationError('ابتدا باید با واردکننده تسویه شود')
                        
        # ارسال پیامک آدرس با استفاده از ایمپورت تاخیری
        sms_api = get_sms_api()
        sms_api.send_address_notification(self)
        
        return self.change_state('ADDRESS_SENT', user, 'آدرس به واردکننده ارسال شد')
        
    def send_to_shipping(self, user):
        """
        ارسال به باربری
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'ADDRESS_SENT':
            raise ValidationError('ابتدا باید آدرس به واردکننده ارسال شود')
        
        return self.change_state('SENT_TO_SHIPPING', user, 'ارسال به باربری انجام شد')
        
    def issue_barnameh(self, user):
        """
        صدور بارنامه
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'SENT_TO_SHIPPING':
            raise ValidationError('ابتدا باید به باربری ارسال شود')
            
        if not hasattr(self, 'barnameh') or not self.barnameh:
            raise ValidationError('شماره بارنامه الزامی است')
            
        # ارسال پیامک بارنامه با استفاده از ایمپورت تاخیری
        sms_api = get_sms_api()
        sms_api.send_barnameh_notification(self)
        
        return self.change_state('BARNAMEH_ISSUED', user, 'بارنامه صادر شد')
        
    def mark_as_delivered(self, user):
        """
        تحویل به مشتری
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'BARNAMEH_ISSUED':
            raise ValidationError('ابتدا باید بارنامه صادر شود')
        
        # تحویل به مشتری انجام شد - بعد از این مرحله باید اختلاف تایید شود
        return self.change_state('DELIVERED', user, 'تحویل به مشتری انجام شد')
        
    def approve_difference(self, user):
        """
        تایید مبلغ اختلاف
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'DELIVERED':
            raise ValidationError('ابتدا باید بار تحویل مشتری شود')
        
        if not self.extelaf_amount and not self.extelaf_weight:
            raise ValidationError('مقادیر اختلاف ثبت نشده است')
        
        # اگر اختلاف از نوع سرک باشد، پیامک ارسال شود
        if self.extelaf_type == 'سرک' and self.extelaf_weight and self.extelaf_amount:
            sms_api = get_sms_api()
            sms_api.send_extelaf_notification(self)
        
        return self.change_state('DIFFERENCE_APPROVED', user, 'مبلغ اختلاف تایید شد')
                
    def deposit_difference(self, user):
        """
        واریز اختلاف (اعم از کسری یا سرک)
        """
        user_role = determine_user_role(user)
        if user_role != 'sales_agent' and user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'DIFFERENCE_APPROVED':
            raise ValidationError('ابتدا باید مبلغ اختلاف تایید شود')
        
        # تغییر وضعیت بدون نیاز به اعتبارسنجی اضافی
        success_message = ''
        if self.extelaf_type == 'کسری':
            success_message = 'کسری واریز شد'
        elif self.extelaf_type == 'سرک':
            success_message = 'سرک واریز شد'
        else:
            success_message = 'اختلاف واریز شد'
            
        self.change_state('DIFFERENCE_DEPOSITED', user, success_message)
        return success_message
        
    def submit_receipt(self, user):
        """
        ثبت رسید
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        valid_states = ['DIFFERENCE_DEPOSITED']
        if self.state not in valid_states:
            raise ValidationError('ابتدا باید کسری یا سرک واریز شود')
        
        return self.change_state('RECEIPT_SUBMITTED', user, 'رسید اختلاف ثبت شد')
        
    def issue_invoice(self, user):
        """
        صدور فاکتور
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'RECEIPT_SUBMITTED':
            raise ValidationError('ابتدا باید رسید ثبت شود')
        
        return self.change_state('INVOICE_ISSUED', user, 'فاکتور صادر شد')
        
    def approve_by_sales(self, user):
        """
        تایید واحد فروش
        """
        user_role = determine_user_role(user)
        if user_role != 'sales_agent' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'RECEIPT_SUBMITTED' and self.state != 'INVOICE_ISSUED':
            raise ValidationError('ابتدا باید رسید ثبت شود یا فاکتور صادر شود')
        
        return self.change_state('SALES_APPROVED', user, 'تایید واحد فروش انجام شد')
        
    def approve_by_logistics(self, user):
        """
        تایید واحد لجستیک
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'RECEIPT_SUBMITTED' and self.state != 'INVOICE_ISSUED' and self.state != 'SALES_APPROVED':
            raise ValidationError('ابتدا باید رسید ثبت شود یا فاکتور صادر شود یا واحد فروش تایید کند')
        
        return self.change_state('LOGISTICS_APPROVED', user, 'تایید واحد لجستیک انجام شد')
        
    def approve_by_financial(self, user):
        """
        تایید واحد مالی
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'INVOICE_ISSUED' and self.state != 'SALES_APPROVED' and self.state != 'LOGISTICS_APPROVED':
            raise ValidationError('ابتدا باید فاکتور صادر شود یا واحدهای دیگر تایید کنند')
        
        # با تایید واحد مالی، خرید تکمیل می‌شود
        return self.change_state('COMPLETED', user, 'تایید واحد مالی انجام شد و خرید تکمیل شد')
        
    def mark_as_urgent(self, user):
        """
        پیگیری فوری
        """
        user_role = determine_user_role(user)
        if user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
        self.is_urgent = True
        self.save(update_fields=['is_urgent'])
        return True
        
    def cancel_purchase(self, user):
        """
        لغو خرید
        """
        user_role = determine_user_role(user)
        if user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
        self.is_canceled = True
        self.save(update_fields=['is_canceled'])
        return True
        
    def archive_purchase(self, user):
        """
        آرشیو خرید
        """
        user_role = determine_user_role(user)
        if user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state in ['PAYMENT_VERIFIED', 'BARNAMEH_ISSUED', 'DELIVERED', 'CANCELED']:
            raise ValidationError('خرید آرشیو شده نمی‌تواند پرداخت شده، ارسال شده، تحویل داده شده یا لغو شده باشد.')
        
        self.is_archived = True
        self.save(update_fields=['is_archived'])
        return True

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
            if len(str(self.tracking_number)) <= 4:
                errors['tracking_number'] = 'شماره پیگیری باید بیشتر از 5 رقم عددی باشد'
        
        if self.amount_paid and (len(str(self.amount_paid)) > 12 or len(str(self.amount_paid)) < 7):
            errors['amount_paid'] = 'مبلغ پرداختی باید بین 7 و 11 رقم باشد'
            
        if self.state == 'PAYMENT_VERIFIED' and not self.amount_paid:
            errors['amount_paid'] = 'برای خریدهای پرداخت شده مبلغ الزامی است'
        elif self.state == 'PAYMENT_VERIFIED' and self.amount_paid <= 100000000:
            errors['amount_paid'] = 'مبلغ پرداختی باید بزرگتر از صد میلیون تومان باشد'

        # وزن را فقط در مواردی که کمتر از 10000 است بررسی کن، تا مقادیر پیش‌فرض بایپس اعتبارسنجی قبول شوند
        if self.order_weight and self.order_weight <= 10000:
            errors['order_weight'] = 'وزن باید بزرگتر از 10 تن باشد'
        
        if not self.customer:
            errors['customer'] = 'انتخاب مشتری الزامی است'
        
        if self.state == 'ARCHIVED':
            if self.state in ['PAYMENT_VERIFIED', 'BARNAMEH_ISSUED', 'DELIVERED', 'CANCELED']:
                errors['state'] = 'خرید آرشیو شده نمی‌تواند پرداخت شده، ارسال شده، تحویل داده شده یا لغو شده باشد.'
                
        # تنها زمانی قیمت‌ها را بررسی کن که مقدار واقعی داشته باشند، نه مقادیر پیش‌فرض بایپس اعتبارسنجی
        if self.customer_price > 0 and (self.customer_price < 50000 or self.customer_price > 300000):
            errors['customer_price'] = 'فی فروش عددی غیرواقعی است.'
            
        if self.company_price > 0 and (self.company_price < 50000 or self.company_price > 300000):
            errors['company_price'] = 'فی خرید عددی غیرواقعی است.'

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
        
        sales_agents = self.customer.sales_agent.all()
        has_non_admin = False
        for agent in sales_agents:
            if not agent.user.is_superuser:
                has_non_admin = True
                break

        # Send SMS notification for new purchase only on creation
        if is_new and self.customer.sms_preference and has_non_admin and self.send_cottage_sms:
            sms_api = get_sms_api()
            sms_api.send_new_purchase_notification(self)
            # تنظیم وضعیت SMS ارسال شده
            if not PurchaseStateChange.objects.filter(purchase=self, new_state='SMS_SENT').exists():
                PurchaseStateChange.objects.create(
                    purchase=self,
                    previous_state='INITIATED',
                    new_state='SMS_SENT',
                    notes='پیامک خودکار ارسال شد'
                )
                self.state = 'SMS_SENT'
                super().save(update_fields=['state'])

        if self.extelaf_weight:
            self.extelaf_amount = self.extelaf_weight * self.cargo.customer_price
            super().save(update_fields=['extelaf_amount'])

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

class PurchaseStateChange(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='state_changes')
    previous_state = models.CharField("وضعیت قبلی", max_length=50, choices=Purchase.STATUS_CHOICES)
    new_state = models.CharField("وضعیت جدید", max_length=50, choices=Purchase.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="تغییر داده شده توسط")
    changed_at = jmodels.jDateTimeField("زمان تغییر", auto_now_add=True)
    notes = models.TextField("توضیحات", blank=True, null=True)

    class Meta:
        verbose_name = "تغییر وضعیت خرید"
        verbose_name_plural = "تغییرات وضعیت خرید"
        ordering = ['-changed_at']

    def __str__(self):
        return f"تغییر از {self.get_previous_state_display()} به {self.get_new_state_display()} در {self.changed_at}"

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

class PurchaseReceipts(models.Model):
    reciept_type=[
        ('bazaargah_receipt', 'رسید بازارگاه'), # logistics_manager sales_agent
        ('non_bazaargah_receipt', 'رسید خارج از بازارگاه'), # logistics_manager sales_agent
        ('deliver', 'اسناد تحویلی'), # logistics_manager sales_agent
        ('extelaf_receipt', 'رسید اختلاف'), # financial_manager sales_agent
        ('invoice', 'فاکتور'), # financial_manager 
    ]
    
    def receipt_upload_path(instance, filename):
        # Generate path like: purchase_receipts/purchase_123/filename
        return f'purchase_receipts/purchase_{instance.purchase.id}/{filename}'
    
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='receipts')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ثبت کننده")
    reciept_type = models.CharField("نوع رسید", max_length=255, choices=reciept_type)
    reciept_file = models.FileField("فایل رسید", upload_to=receipt_upload_path, null=True, blank=True)
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)
    
    class Meta:
        verbose_name = "رسید خرید"
        verbose_name_plural = "رسیدهای خرید"
    
    def __str__(self):
        return f"{self.reciept_type} - {self.purchase.purchase_number} - {self.created_at}"

