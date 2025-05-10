from django.db import models, transaction
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils import timezone
from .CustomerModel import Customer
from .CargoProductModel import CargoProduct
from .SalesAgentModel import SalesAgent
from django.contrib import messages
from django.contrib.auth.models import User
from ERP.models.NotificationService import NotificationService
from ERP.models.Notification import Notification
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
import random
from django.db.models import Sum, Q, F
import re

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
        ('PAYMENT_VERIFIED', 'ثبت خرید در بازارگاه'),  # system (with bazaargah api :D )
        ('ALLOCATION_APPROVED', 'ثبت تخصیص در بازارگاه'),  # system #sms
        # ('VENDOR_SETTLED', 'تسویه با واردکننده'),  # financial_manager #sms
        ('ADDRESS_SENT', 'ارسال آدرس به واردکننده'), # logistics_manager #sms
        ('SENT_TO_SHIPPING', 'در انتظار بارنامه'), # logistics_manager
        ('SENT_TO_SHIPPING', 'صدور بارنامه (ناقص)'), # logistics_manager #sms
        ('BARNAMEH_ISSUED', 'صدور بارنامه'), # system
        ('BARNAMEH_INCOMPLETE', 'بستن خرید در بازارگاه'), # system #sms
        ('DIFFERENCE_APPROVED', 'پرداخت کسری'), # financial_manager
        ('DIFFERENCE_APPROVED', 'دریافت سرک'), # financial_manager
        # ('RECEIPT_SUBMITTED', 'ثبت رسید واریزی اختلاف'), # financial_manager
        ('FULLY_SETTLED', 'تسویه کامل'), # financial_manager
        ('INVOICE_ISSUED', 'صدور فاکتور'), # financial_manager

        ('CANCELED', 'لغو شده'), # admin
        ('ARCHIVED', 'آرشیو شده'), # admin
    ]
    
    id = models.AutoField(primary_key=True)
    state = models.CharField("وضعیت", max_length=50, choices=STATUS_CHOICES, default='INITIATED')
    invoice_id = models.CharField(max_length=20, verbose_name='کد درون سازمانی', unique=True, editable=False, blank=True, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="مشتری", help_text="ارتباط یک‌به‌یک با مشتری از طریق شماره تلفن یا آیدی", related_name='purchases_made', null=True, blank=True)
    sales_agent = models.ManyToManyField(SalesAgent, through='PuchaseSalesAgent', verbose_name="کارشناس فروش", blank=True, related_name='purchase_assignments')
    address = models.TextField("آدرس", blank=True, null=True)
    description = models.TextField("توضیحات", blank=True, null=True)
    company_price = models.PositiveIntegerField("فی خرید(ریال)", default=0)
    customer_price = models.PositiveIntegerField("فی فروش(ریال)", default=0)

    purchase_number = models.CharField("شماره خرید بازارگاه", max_length=7, blank=True, null=True, unique=True)
    tracking_number = models.CharField("شماره پیگیری", max_length=6, blank=True, null=True, unique=True)
    shenase_takhsis = models.CharField("شناسه تخصیص", max_length=255, blank=True, null=True, unique=False)
    code_melli_tahvil = models.CharField("کد ملی تحویل", max_length=255, blank=True, null=True)
    bazaargah_phone_number = models.CharField("شماره تلفن بازارگاه", max_length=11, blank=True, null=True)
    buyer_name = models.CharField("نام خریدار", max_length=255, blank=True, null=True)
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

    is_fully_tasvied = models.BooleanField("تسویه کامل", default=False)
    is_factored = models.BooleanField("ثبت فاکتور", default=False)


    PRIORITY_CHOICES = [
        ('low', 'عادی'),
        ('medium', 'مهم'),
        ('high', 'فوری'),
        ('critical', 'بحرانی')
    ]
    
    # اضافه کردن فیلد جدید
    priority = models.CharField(
        "اولویت",
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='low'
    )
    priority_reason = models.TextField(
        "دلیل اولویت",
        blank=True,
        null=True
    )

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
        
        # اگر مشتری تنظیمات ارسال پیامک را فعال کرده باشد، پیامک ارسال می‌کنیم
        try:
            if self.customer and self.customer.sms_preference:
                from sms_api.apis import send_purchase_status_notification
                notification_sent = send_purchase_status_notification(self)
                
                if notification_sent:
                    print(f"Notification sent for state change to {new_state} for purchase {self.invoice_id}")
                    # Add a note to the purchase history
                    PurchaseHistory.objects.create(
                        purchase=self,
                        user=user,
                        changes=f"ارسال پیامک تغییر وضعیت به {self.get_state_display()}"
                    )
                else:
                    print(f"Notification not sent for purchase {self.invoice_id}. Check SMS settings and templates.")
        except Exception as e:
            import traceback
            print(f"Error sending notification for status change to {new_state} for purchase {self.invoice_id}: {e}")
            print(traceback.format_exc())
            # Log the error to the purchase history
            PurchaseHistory.objects.create(
                purchase=self,
                user=user,
                changes=f"خطا در ارسال پیامک: {str(e)}"
            )
        
        return True

    def confirm_bazaargah(self, user):
        """
        تایید خرید در بازارگاه - این تابع به خاطر سازگاری با کد قبلی حفظ شده است
        در سیستم جدید، تاییدیه بازارگاه از طریق API انجام می‌شود
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.type != 'bazaargah':
            raise ValidationError('این خرید خارج از بازارگاه است')
            
        if not self.purchase_number:
            raise ValidationError('شماره خرید الزامی است')
        
        notification_message = (
            f"خرید {self.invoice_id} در بازارگاه تایید شد. "
            f"منتظر تایید پرداخت توسط واحد مالی"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تایید در بازارگاه",
            notification_type='purchase',
            priority='medium'
        )
        
        # تغییر مستقیم به PAYMENT_VERIFIED به جای BAZAARGAH_CONFIRMED
        return self.change_state('PAYMENT_VERIFIED', user, 'تایید شده در بازارگاه و تایید نشستن در بازارگاه')
        
    def verify_payment(self, user):
        """
        تایید پرداخت - در سیستم جدید، پرداخت توسط API تایید می‌شود
        به خاطر سازگاری با کد قبلی، این تابع همچنان وجود دارد
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        # در سیستم جدید، تایید پرداخت بازارگاه از طریق API انجام می‌شود
        # بنابراین بررسی state قبلی لزومی ندارد
        if not self.amount_paid or self.amount_paid <= 10000000:
            raise ValidationError('مبلغ پرداختی باید بزرگتر از 10 میلیون ریال باشد')
            
        # کسر از موجودی محصول
        if not self.is_weight_costed and self.cargo:
            self.is_weight_costed = True
            self.cargo.weight -= self.order_weight
            self.cargo.save()
            
        notification_message = (
            f"پرداخت خرید {self.invoice_id} به مبلغ {self.amount_paid:,} ریال "
            f"برای مشتری {self.customer.name} تایید شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تایید پرداخت",
            notification_type='payment',
            priority='high'
        )
        
        # وضعیت خرید به تایید نشستن در بازارگاه تغییر می‌کند
        return self.change_state('PAYMENT_VERIFIED', user, 'تایید مالی انجام شد')

        
    def register_allocation(self, user):
        """
        ثبت تخصیص - در سیستم جدید، تخصیص از طریق API تایید می‌شود
        به خاطر سازگاری با کد قبلی، این تابع همچنان وجود دارد
        """
        user_role = determine_user_role(user)
        if user_role != 'sales_agent' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if not self.shenase_takhsis:
            raise ValidationError('شناسه تخصیص الزامی است')
        
        notification_message = (
            f"شناسه تخصیص برای خرید {self.invoice_id} "
            f"توسط {user.get_full_name()} ثبت شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="ثبت شناسه تخصیص",
            notification_type='allocation',
            priority='high'
         )
    
        # در سیستم جدید، مستقیما به وضعیت تایید تخصیص می‌رویم
        return self.change_state('ALLOCATION_APPROVED', user, 'تخصیص ثبت و تایید شد')
        
    def approve_allocation(self, user):
        """
        تایید تخصیص - این تابع در سیستم جدید صرفا برای سازگاری با کد قدیمی حفظ شده است
        در سیستم جدید، تخصیص از طریق API تایید می‌شود
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        # در سیستم جدید، نیازی به بررسی وضعیت قبلی نیست، چون با API تایید می‌شود
        # اما برای اطمینان، تایید می‌کنیم که خرید در وضعیت تایید پرداخت باشد
        if self.state != 'PAYMENT_VERIFIED' and self.state != 'ALLOCATION_APPROVED':
            raise ValidationError('ابتدا باید پرداخت تایید شود')
        
        notification_message = (
            f"تخصیص خرید {self.invoice_id} "
            f"توسط {user.get_full_name()} تایید شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تایید تخصیص",
            notification_type='allocation',
            priority='high'
        )
        
        return self.change_state('ALLOCATION_APPROVED', user, 'تخصیص تایید شد')
        
    def settle_with_vendor(self, user):
        """
        تسویه با واردکننده
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        # تغییر شرایط براساس وضعیت‌های جدید
        if self.state != 'PAYMENT_VERIFIED' and self.state != 'ALLOCATION_APPROVED':
            raise ValidationError('ابتدا باید پرداخت و تخصیص تایید شود')
        
        notification_message = (
            f"تسویه با واردکننده برای خرید {self.invoice_id} "
            f"به مبلغ {self.amount_paid:,} ریال انجام شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تسویه با واردکننده",
            notification_type='payment',
            priority='high'
        )
        
        return self.change_state('VENDOR_SETTLED', user, 'تسویه با واردکننده انجام شد')
        
    def send_address_to_vendor(self, user):
        """
        ارسال آدرس به واردکننده
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if not self.address:
            raise ValidationError('آدرس باید ثبت شده باشد')

        notification_message = (
            f"آدرس مشتری {self.customer.name} برای خرید {self.invoice_id} "
            f"توسط {user.get_full_name()} به واردکننده ارسال شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="ارسال آدرس به واردکننده",
            notification_type='address',
            priority='medium'
        )
        
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
        
        notification_message = (
            f"خرید {self.invoice_id} به وزن {self.order_weight:,} کیلوگرم "
            f"به باربری ارسال شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="ارسال به باربری",
            notification_type='shipping',
            priority='medium'
        )
        
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
            
        notification_message = (
            f"بارنامه خرید {self.invoice_id} به شماره {self.barnameh} "
            f"برای مشتری {self.customer.name} صادر شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="صدور بارنامه",
            notification_type='shipping',
            priority='medium'
        )
        
        return self.change_state('BARNAMEH_ISSUED', user, 'بارنامه صادر شد')

    def mark_barnameh_incomplete(self, user):
        """
        ثبت بارنامه ناقص
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'SENT_TO_SHIPPING' and self.state != 'BARNAMEH_ISSUED':
            raise ValidationError('این وضعیت تنها برای خریدهایی است که به باربری ارسال شده و یا بارنامه صادر شده است')
            
        notification_message = (
            f"بارنامه خرید {self.invoice_id} "
            f"توسط {user.get_full_name()} ناقص اعلام شد. نیاز به پیگیری دارد."
        )
        self.notify_relevant_users(
            message=notification_message,
            title="بارنامه ناقص",
            notification_type='shipping',
            priority='high'
        )
        
        return self.change_state('BARNAMEH_INCOMPLETE', user, 'بارنامه ناقص اعلام شد')

        
    def mark_as_delivered(self, user):
        """
        تحویل به مشتری
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'BARNAMEH_ISSUED' and self.state != 'BARNAMEH_INCOMPLETE':
            raise ValidationError('ابتدا باید بارنامه صادر شود یا وضعیت بارنامه ناقص داشته باشد')
        
        notification_message = (
            f"خرید {self.invoice_id} به وزن {self.delivered_weight:,} کیلوگرم "
            f"به مشتری {self.customer.name} تحویل داده شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تحویل به مشتری",
            notification_type='delivery',
            priority='medium'
        )
        
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
        
        notification_message = (
            f"اختلاف {self.extelaf_type} خرید {self.invoice_id} "
            f"به میزان {self.extelaf_weight:,} کیلوگرم "
            f"و مبلغ {self.extelaf_amount:,} ریال تایید شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تایید اختلاف",
            notification_type='difference',
            priority='high'
        )
        
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
        
        notification_message = (
            f"رسید واریز برای خرید {self.invoice_id} "
            f"توسط {user.get_full_name()} ثبت شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="ثبت رسید",
            notification_type='system',
            priority='medium'
        )
        
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
        
        notification_message = (
            f"فاکتور خرید {self.invoice_id} به مبلغ {self.amount_paid:,} ریال "
            f"صادر شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="صدور فاکتور",
            notification_type='system',
            priority='medium'
        )
        
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
        
        notification_message = (
            f"خرید {self.invoice_id} توسط واحد فروش "
            f"({user.get_full_name()}) تایید نهایی شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تایید واحد فروش",
            notification_type='system',
            priority='medium'
        )
        
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
        
        notification_message = (
            f"خرید {self.invoice_id} به مبلغ {self.amount_paid:,} ریال "
            f"برای مشتری {self.customer.name} تکمیل شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="تکمیل خرید",
            notification_type='system',
            priority='medium'
        )
        
        return self.change_state('COMPLETED', user, 'تایید واحد مالی انجام شد و خرید تکمیل شد')
            
    def mark_as_urgent(self, user):
        """
        پیگیری فوری
        """
        user_role = determine_user_role(user)
        if user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
        
        notification_message = (
            f"⚠️ خرید {self.invoice_id} به حالت فوری تغییر وضعیت داد. "
            f"لطفا در اسرع وقت پیگیری شود."
        )
        self.notify_relevant_users(
            message=notification_message,
            title="پیگیری فوری",
            notification_type='system',
            priority='critical'
        )
        
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
        
        notification_message = (
            f"⚠️ خرید {self.invoice_id} توسط {user.get_full_name()} لغو شد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="لغو خرید",
            notification_type='system',
            priority='critical'
    )

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
        if self.customer_price > 0 and self.customer_price < 50000:
            errors['customer_price'] = 'فی فروش باید حداقل 50000 ریال باشد.'
            
        if self.company_price > 0 and self.company_price < 50000:
            errors['company_price'] = 'فی خرید باید حداقل 50000 ریال باشد.'

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
            self.invoice_id = f"{factor_code}{str(new_serial).zfill(6)}"

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
        if is_new and self.customer.sms_preference and has_non_admin:
            if self.send_cottage_sms:
                from sms_api.apis import send_purchase_status_notification
                send_purchase_status_notification(self)
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
            self.extelaf_amount = self.extelaf_weight * self.customer_price
            super().save(update_fields=['extelaf_amount'])


    def send_notification(self, user, title, message, notification_type='purchase', priority='medium'):
        """ارسال نوتیفیکیشن برای کاربر"""
        NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority
        )

    def notify_relevant_users(self, message, title, notification_type='purchase', priority='medium'):
        """ارسال نوتیفیکیشن به کاربران مرتبط"""
        # ارسال به نماینده فروش
        for agent in self.customer.sales_agent.all():
            if agent.user:
                self.send_notification(agent.user, title, message, notification_type, priority)
        
        # ارسال به مدیر لجستیک
        from core._models import LogisticsManager
        logistics_managers = LogisticsManager.objects.all()
        for manager in logistics_managers:
            if manager.user:
                self.send_notification(manager.user, title, message, notification_type, priority)

        # ارسال به مدیر مالی
        from core._models import FinancialManager
        financial_managers = FinancialManager.objects.all()
        for manager in financial_managers:
            if manager.user:
                self.send_notification(manager.user, title, message, notification_type, priority)


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
    weight = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="وزن", null=True, blank=True)
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

class PriceHistory(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    old_price = models.DecimalField(max_digits=12, decimal_places=0)
    new_price = models.DecimalField(max_digits=12, decimal_places=0)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    
    class Meta:
        ordering = ['-changed_at']

class PurchaseApproval(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    step = models.CharField(max_length=50)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approved_at = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(blank=True)
    
    def notify_next_approver(self):
        next_approver = self.get_next_approver()
        if next_approver:
            # ارسال نوتیفیکیشن به تأییدکننده بعدی
            Notification.objects.create(
                user=next_approver,
                title="درخواست تأیید خرید",
                message=f"خرید {self.purchase.invoice_id} منتظر تأیید شماست"
            )

class PuchaseSalesAgent(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='purchase_sales_agents')
    sales_agent = models.ForeignKey(SalesAgent, on_delete=models.CASCADE, related_name='purchase_relations')
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)
    
    class Meta:
        verbose_name = "کارشناس فروش خرید"
        verbose_name_plural = "کارشناس فروش خریدها"

class PurchaseEditLog(models.Model):
    """
    مدل برای ذخیره تاریخچه تغییرات فیلدهای خرید
    """
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='edit_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر ویرایش کننده")
    field_name = models.CharField("نام فیلد", max_length=100)
    old_value = models.TextField("مقدار قبلی", blank=True, null=True)
    new_value = models.TextField("مقدار جدید", blank=True, null=True)
    edit_time = jmodels.jDateTimeField("زمان ویرایش", auto_now_add=True)
    is_revert = models.BooleanField("بازگشت به نسخه قبلی", default=False)
    reverted_log = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='revert_logs', verbose_name="لاگ بازگشتی")
    
    class Meta:
        verbose_name = "تاریخچه ویرایش خرید"
        verbose_name_plural = "تاریخچه‌های ویرایش خرید"
        ordering = ['-edit_time']
        
    def __str__(self):
        return f"ویرایش {self.field_name} خرید {self.purchase.invoice_id} در {self.edit_time}"
        
    def get_field_display_name(self):
        """
        نام نمایشی فیلد را برمی‌گرداند
        """
        field_mappings = {
            'invoice_id': 'کد درون سازمانی',
            'purchase_number': 'شماره خرید',
            'order_weight': 'وزن سفارش',
            'state': 'وضعیت',
        }
        return field_mappings.get(self.field_name, self.field_name)
