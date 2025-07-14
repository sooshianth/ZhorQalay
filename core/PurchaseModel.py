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
from .CustomerModel import FIELD_OF_ACTIVITY
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
import random
from django.db.models import Sum, Q, F
import re
from core.decorators.det_user_role import determine_user_role
import logging

logger = logging.getLogger("core_purchase")


class Purchase(models.Model):
    # وضعیت‌های مختلف خرید
    STATUS_CHOICES = [
        ('INITIATED', 'شروع شده'), # system
        ('SMS_SENT', 'پیامک ارسال شده'), # system
        ('PAYMENT_VERIFIED', 'ثبت خرید در بازارگاه'),  # system (with bazaargah api :D )
        ('ALLOCATION_APPROVED', 'ثبت تخصیص در بازارگاه'),  # system #sms
        ('ADDRESS_SENT', 'ارسال آدرس به واردکننده'), # logistics_manager #sms
        ('WAITING_FOR_BARNAMEH', 'در انتظار بارنامه'), # logistics_manager
        ('BARNAMEH_INCOMPLETE', 'صدور بارنامه (ناقص)'), # logistics_manager #sms
        ('BARNAMEH_ISSUED', 'صدور بارنامه'), # system
        ('PURCHASE_CLOSED', 'بستن خرید در بازارگاه'), # system #sms
        ('PAY_KASRI', 'پرداخت کسری'), # financial_manager
        ('RECIEIVE_SARAK', 'دریافت سرک'), # financial_manager
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
    address = models.TextField("آدرس خریدار", blank=True, null=True)
    description = models.TextField("توضیحات", blank=True, null=True)
    company_price = models.PositiveIntegerField("فی خرید(ریال)", default=0)
    customer_price = models.PositiveIntegerField("فی فروش(ریال)", default=0)
    factor_code = models.BooleanField("فاکتور کد", default=False)
    
    purchase_number = models.CharField("شماره خرید بازارگاه", max_length=7, blank=True, null=True, unique=True)
    tracking_number = models.CharField("شماره پیگیری", max_length=6, blank=True, null=True)
    shenase_takhsis = models.CharField("شناسه تخصیص", max_length=255, blank=True, null=True, unique=False)
    code_melli_tahvil = models.CharField("کد ملی تحویل", max_length=255, blank=True, null=True)
    bazaargah_phone_number = models.CharField("شماره تلفن بازارگاه", max_length=15, blank=True, null=True)
    buyer_name = models.CharField("نام خریدار", max_length=255, blank=True, null=True)
    tahvil_phone_number = models.CharField("شماره تلفن تحویل", max_length=15, blank=True, null=True)
    bazaargah_customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, verbose_name="مشتری بازارگاه", null=True, blank=True, related_name='bazaargah_purchases')
    unique_sales_agent_code = models.CharField("کد کارشناس فروش", max_length=50, blank=True, null=True)
    unique_sales_agent = models.ForeignKey(SalesAgent, on_delete=models.SET_NULL, verbose_name="کارشناس فروش", null=True, blank=True, related_name='unique_sales_agent_purchases')

    send_cottage_sms = models.BooleanField('ارسال پیامک کوتاژ', default=True)
    total_weight = models.PositiveIntegerField("وزن کل (کیلوگرم)", default=0, null=True, blank=True)
    order_weight = models.PositiveIntegerField("وزن سفارش (کیلوگرم)", default=0)
    delivered_weight = models.PositiveIntegerField("وزن بارنامه شده (کیلوگرم)", default=0)
    cargo = models.ForeignKey(CargoProduct,on_delete=models.SET_NULL, verbose_name="کوتاژ", null=True, blank=True, related_name='purchases')
    type = models.CharField("نوع خرید", max_length=25, default='bazaargah', choices=[('bazaargah', 'بازارگاه'), ('non_bazaargah', 'خارج از بازارگاه')])
    amount_paid = models.PositiveBigIntegerField("مبلغ پرداختی(ریال)", blank=True, null=True)
    payment_method = models.CharField("شیوۀ پرداخت", max_length=6, choices=[('نقدی', 'نقدی'), ('توافقی', 'توافقی')], default="نقدی")
    created_at = jmodels.jDateTimeField("تاریخ ثبت", default=timezone.now)
    updated_at  = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True, blank=True, null=True)
    
    barbary_confidential_number = models.CharField("شماره باربری محرمانه", max_length=50, blank=True, null=True, 
                                                  help_text="شماره محرمانه باربری برای ادمین یا مالی  ")
    barbary_customer_number = models.CharField("شماره باربری مشتری", max_length=50, blank=True, null=True,
                                             help_text="شماره ارائه شده به مشتری از طرف باربری")
    
    delivery_receiver_name = models.CharField("نام تحویل گیرنده", max_length=255, blank=True, null=True)
    buyer_national_id = models.CharField("شناسه ملی خریدار", max_length=20, blank=True, null=True)

    buyer_user_type = models.CharField("نوع کاربری خریدار", max_length=20, choices=FIELD_OF_ACTIVITY, blank=True, null=True)
    
    # فیلدهای آدرس و تحویل
    unique_delivery_id = models.CharField("شناسه یکتا تحویل", max_length=50, blank=True, null=True, unique=True)
    delivery_address = models.TextField("آدرس تحویل", blank=True, null=True)
    delivery_postal_code = models.CharField("کد پستی تحویل", max_length=10, blank=True, null=True)
    
    # نوع خودرو حمل
    VEHICLE_TYPE_CHOICES = [
        ('trailer', 'تریلی'),
        ('single', 'تک'),
        ('double', 'جفت'),
    ]
    vehicle_type = models.CharField("نوع خودرو حمل", max_length=20, choices=VEHICLE_TYPE_CHOICES,blank=True, null=True)


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

    ready_for_invoice = models.BooleanField("آماده فاکتور", default=False)
    purchase_mabna_invoice = models.PositiveBigIntegerField("فاکتور خرید مبنا", blank=True, null=True)
    sales_mabna_invoice = models.PositiveBigIntegerField("فاکتور فروش مبنا", blank=True, null=True)
    mabna_profit = models.PositiveBigIntegerField("سود مبنا", blank=True, null=True)

    wallet_index = models.CharField("شاخص محاسبه کیف پول", max_length=1, default='0', choices=[('0', 'وزن سفارش'), ('1', 'وزن تحویلی')])
    is_address_sent = models.CharField('آیا آدرس به واردکننده ارسال شده اس؟', max_length=1, default='0', choices=[('0', "ارسال نشده"),('1', "ارسال شده")])

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

    FACTOR_CHOICES = [
        ('not_factored', 'فاکتور صادرنشده'),
        ('naghes_factored', 'فاکتور ناقص'),
        ('factored', 'فاکتور صادر شده'),
    ]
    factor_status = models.CharField("وضعیت فاکتور", max_length=20, choices=FACTOR_CHOICES, default='not_factored')
    is_naghes_factored = models.BooleanField("فاکتور ناقص", default=False)

    def is_merged_purchase(self):
        """
        بررسی اینکه آیا این خرید بازارگاه قبلاً با خرید دستی ادغام شده است یا نه
        
        منطق جدید:
        - خرید دستی (بدون purchase_number) هیچ‌وقت ادغام شده نیست چون خودش ماده اولیه ادغام است
        - خرید API (دارای purchase_number):
          * اگر unique_sales_agent نداشته باشد = ادغام نشده
          * اگر unique_sales_agent ادمین (سوپریوزر) باشد = ادغام نشده (فقط API تخصیص داده)
          * اگر unique_sales_agent کارشناس فروش عادی باشد = ادغام شده
        """
        if not self.purchase_number:
            # خرید دستی - هیچ‌وقت ادغام شده نیست
            return False
        else:
            # خرید API - بررسی وضعیت unique_sales_agent
            if not self.unique_sales_agent:
                # هیچ کارشناس فروشی تخصیص نیافته = ادغام نشده
                return False
            elif self.unique_sales_agent.user and self.unique_sales_agent.user.is_superuser:
                # کارشناس فروش ادمین است = ادغام نشده (فقط API تخصیص داده)
                return False
            else:
                # کارشناس فروش عادی = ادغام شده
                return True
    
    def can_be_merged(self):
        """
        بررسی اینکه آیا این خرید می‌تواند ادغام شود یا نه
        
        منطق جدید:
        - خرید دستی (بدون purchase_number) همیشه می‌تواند ادغام شود
        - خرید API (دارای purchase_number):
          * اگر unique_sales_agent نداشته باشد = قابل ادغام
          * اگر unique_sales_agent ادمین (سوپریوزر) باشد = قابل ادغام
          * اگر unique_sales_agent کارشناس فروش عادی باشد = غیرقابل ادغام (قبلاً ادغام شده)
        """
        if not self.purchase_number:
            # خرید دستی - همیشه می‌تواند ادغام شود
            return True
        else:
            # خرید API - بررسی وضعیت unique_sales_agent
            if not self.unique_sales_agent:
                # هیچ کارشناس فروشی تخصیص نیافته = قابل ادغام
                return True
            elif self.unique_sales_agent.user and self.unique_sales_agent.user.is_superuser:
                # کارشناس فروش ادمین است = قابل ادغام (فقط API تخصیص داده)
                return True
            else:
                # کارشناس فروش عادی = غیرقابل ادغام (قبلاً ادغام شده)
                return False

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
        
    def wait_for_barnameh(self, user):
        """
        در انتظار بارنامه
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'ADDRESS_SENT':
            raise ValidationError('ابتدا باید آدرس به واردکننده ارسال شود')
        
        notification_message = (
            f"خرید {self.invoice_id} به وزن {self.order_weight:,} کیلوگرم "
            f"در انتظار صدور بارنامه قرار گرفت"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="در انتظار بارنامه",
            notification_type='shipping',
            priority='medium'
        )
        
        return self.change_state('WAITING_FOR_BARNAMEH', user, 'در انتظار بارنامه قرار گرفت')
        
    def issue_barnameh(self, user):
        """
        صدور بارنامه
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'WAITING_FOR_BARNAMEH':
            raise ValidationError('ابتدا باید وضعیت در انتظار بارنامه ثبت شود')
            
        # حذف بررسی فیلد barnameh که وجود ندارد
        # بارنامه‌ها در اپلیکیشن جداگانه مدیریت می‌شوند
        
        notification_message = (
            f"بارنامه خرید {self.invoice_id} "
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
            
        if self.state != 'WAITING_FOR_BARNAMEH' and self.state != 'BARNAMEH_ISSUED':
            raise ValidationError('این وضعیت تنها برای خریدهایی است که در انتظار بارنامه هستند یا بارنامه صادر شده است')
            
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
        
    def close_purchase(self, user):
        """
        بستن خرید در بازارگاه
        """
        user_role = determine_user_role(user)
        if user_role != 'logistics_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'BARNAMEH_ISSUED' and self.state != 'BARNAMEH_INCOMPLETE':
            raise ValidationError('ابتدا باید بارنامه صادر شود یا وضعیت بارنامه ناقص داشته باشد')
        
        notification_message = (
            f"خرید {self.invoice_id} به وزن {self.delivered_weight:,} کیلوگرم "
            f"در بازارگاه به حالت بسته شده تغییر وضعیت داد"
        )
        self.notify_relevant_users(
            message=notification_message,
            title="بستن خرید در بازارگاه",
            notification_type='delivery',
            priority='medium'
        )
        
        return self.change_state('PURCHASE_CLOSED', user, 'خرید در بازارگاه بسته شد')
        
    def approve_difference(self, user):
        """
        تایید مبلغ اختلاف
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'PURCHASE_CLOSED':
            raise ValidationError('ابتدا باید خرید در بازارگاه بسته شود')
        
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
                
    def fully_settle(self, user):
        """
        تسویه کامل
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'DIFFERENCE_APPROVED' and self.state != 'PURCHASE_CLOSED':
            raise ValidationError('ابتدا باید مبلغ اختلاف تایید شود یا خرید در بازارگاه بسته شده باشد')
        
        # تغییر وضعیت بدون نیاز به اعتبارسنجی اضافی
        notification_message = (
            f"خرید {self.invoice_id} به صورت کامل تسویه شد"
        )
            
        self.notify_relevant_users(
            message=notification_message,
            title="تسویه کامل",
            notification_type='system',
            priority='medium'
        )
        
        self.is_fully_tasvied = True
        self.save(update_fields=['is_fully_tasvied'])
        
        return self.change_state('FULLY_SETTLED', user, 'تسویه کامل انجام شد')
        
    def issue_invoice(self, user):
        """
        صدور فاکتور
        """
        user_role = determine_user_role(user)
        if user_role != 'financial_manager' and user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state != 'FULLY_SETTLED':
            raise ValidationError('ابتدا باید تسویه کامل انجام شود')
        
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
        
        # تنظیم is_factored روی True که خودکار factor_code را هم True می‌کند
        self.is_factored = True
        # factor_code خودکار در save method تنظیم می‌شود
        self.save(update_fields=['is_factored', 'factor_code'])
        
        return self.change_state('INVOICE_ISSUED', user, 'فاکتور صادر شد')
        
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
        return self.change_state('CANCELED', user, 'خرید لغو شد')
        
    def archive_purchase(self, user):
        """
        آرشیو خرید
        """
        user_role = determine_user_role(user)
        if user_role != 'admin':
            raise ValidationError('شما اجازه دسترسی به این قسمت را ندارید')
            
        if self.state in ['PAYMENT_VERIFIED', 'BARNAMEH_ISSUED', 'PURCHASE_CLOSED', 'CANCELED']:
            raise ValidationError('خرید آرشیو شده نمی‌تواند پرداخت شده، ارسال شده، بسته شده یا لغو شده باشد.')
        
        self.is_archived = True
        self.save(update_fields=['is_archived'])
        return self.change_state('ARCHIVED', user, 'خرید آرشیو شد')

    class Meta:
        verbose_name = "خرید"
        verbose_name_plural = "خریدها"
    
    def __str__(self):
        return f"خرید {self.purchase_number} - {self.customer.name} در تاریخ {self.created_at}"

    def clean(self):
        errors = {}
        if self.purchase_number:
            if len(str(self.purchase_number)) < 7 or not self.purchase_number.isdigit():
                errors['purchase_number'] = 'شماره خرید باید 7 رقم یا بیشتر باشد'

        if self.tracking_number:
            if len(str(self.tracking_number)) <= 4:
                errors['tracking_number'] = 'شماره پیگیری باید بیشتر از 5 رقم عددی باشد'
        
        # بررسی اینکه خرید بازارگاه (دارای purchase_number) که قبلاً ادغام شده نتواند دوباره ادغام شود
        if self.purchase_number and self.bazaargah_customer:
            # این یک خرید API است که قبلاً ادغام شده - بررسی محدودیت‌های اضافی
            pass
        
            
        if self.state == 'PAYMENT_VERIFIED' and not self.amount_paid:
            errors['amount_paid'] = 'برای خریدهای پرداخت شده مبلغ الزامی است'
        elif self.state == 'PAYMENT_VERIFIED' and self.amount_paid <= 40000000:
            errors['amount_paid'] = 'مبلغ پرداختی باید بزرگتر از 4 میلیون تومان باشد'

        # وزن را فقط در مواردی که کمتر از 10000 است بررسی کن، تا مقادیر پیش‌فرض بایپس اعتبارسنجی قبول شوند
        if self.order_weight and self.order_weight <= 1000:
            errors['order_weight'] = 'وزن باید بزرگتر از 1 تن باشد'
                
        if self.state == 'ARCHIVED':
            if self.state in ['PAYMENT_VERIFIED', 'BARNAMEH_ISSUED', 'PURCHASE_CLOSED', 'CANCELED']:
                errors['state'] = 'خرید آرشیو شده نمی‌تواند پرداخت شده، ارسال شده، بسته شده یا لغو شده باشد.'
                
        # تنها زمانی قیمت‌ها را بررسی کن که مقدار واقعی داشته باشند، نه مقادیر پیش‌فرض بایپس اعتبارسنجی
        if self.customer_price > 0 and self.customer_price < 10000:
            errors['customer_price'] = 'فی فروش باید حداقل 10000 ریال باشد.'
            
        if self.company_price > 0 and self.company_price < 10000:
            errors['company_price'] = 'فی خرید باید حداقل 10000 ریال باشد.'
            
        # اعتبارسنجی فیلدهای جدید
        if self.buyer_national_id:
            # حذف فاصله‌ها و کاراکترهای غیرضروری
            national_id = ''.join(c for c in str(self.buyer_national_id) if c.isdigit())
            if len(national_id) not in [8, 10, 11]:  # کد ملی، شناسه حقوقی، یا شماره گذرنامه
                errors['buyer_national_id'] = 'شناسه ملی باید 8، 10 یا 11 رقم باشد'
            
        if self.delivery_postal_code:
            # حذف فاصله‌ها و بررسی طول کد پستی
            postal_code = ''.join(c for c in str(self.delivery_postal_code) if c.isdigit())
            if len(postal_code) != 10:
                errors['delivery_postal_code'] = 'کد پستی باید 10 رقم باشد'
                
        if self.unique_delivery_id:
            # بررسی یکتا بودن شناسه تحویل
            existing = Purchase.objects.filter(unique_delivery_id=self.unique_delivery_id).exclude(pk=self.pk)
            if existing.exists():
                errors['unique_delivery_id'] = 'این شناسه تحویل قبلاً استفاده شده است'

        if errors:
            raise ValidationError(errors)
            
    def save(self, *args, **kwargs):

        is_new = not self.pk  # Check if this is a new instance

        # 🧮 محاسبه فاکتور مبنا و factor_code
        if self.ready_for_invoice or self.is_factored:
            self.factor_code = True
        else:
            self.factor_code = False


        # 🏗️ محاسبه فاکتورهای مبنا و سود مبنا
        # محاسبه همیشه انجام می‌شود، حتی اگر قیمت‌ها صفر باشند
        company_price = self.company_price or 0
        customer_price = self.customer_price or 0
        
        # تعیین وزن مبنا بر اساس factor_code
        if self.factor_code:
            # اگر آماده فاکتور یا صدور فاکتور است، وزن بارنامه شده مبنا است
            # اگر وزن بارنامه شده 0 باشد، همه محاسبات باید 0 شوند
            base_weight = self.delivered_weight or 0
            # اگر delivered_weight صفر است، محاسبه نکن
            if base_weight == 0:
                base_weight = 0
        else:
            # در غیر این صورت وزن خرید مبنا است
            base_weight = self.order_weight or 0
        
        # محاسبه فاکتور خرید مبنا
        self.purchase_mabna_invoice = company_price * base_weight
        
        # محاسبه فاکتور فروش مبنا
        self.sales_mabna_invoice = customer_price * base_weight
        
        # محاسبه سود مبنا
        self.mabna_profit = self.sales_mabna_invoice - self.purchase_mabna_invoice
        

                
        # مکانیزم خودکار همگام‌سازی کارشناس فروش و نام
        try:
            
            # حالت سوم: کد کارشناس فروش موجود است اما آبجکت موجود نیست
            if self.unique_sales_agent_code:
                sales_agent = SalesAgent.objects.filter(factor_code=self.unique_sales_agent_code).first()
                if sales_agent:
                    self.unique_sales_agent = sales_agent
                    logger.info(f"✅ کارشناس فروش {sales_agent.name} با کد {sales_agent.factor_code} برای خرید {self.pk or 'جدید'} تنظیم شد")
                else:
                    logger.warning(f"⚠️ کارشناس فروش با کد '{self.unique_sales_agent_code}' یافت نشد")
                
        except Exception as e:
            logger.warning(f"❌ خطا در همگام‌سازی کارشناس فروش: {str(e)}")
                
        if not self.invoice_id:
            factor_code = '99'  # Código por defecto para administrador
            
            if self.customer and self.customer.sales_agent.exists():
                if len(self.customer.sales_agent.all()) > 1:
                    factor_code = '88'  # Código para múltiples agentes
                else:
                    try:
                        # Obtenemos el primer (y único) agente
                        sales_agent = self.customer.sales_agent.first()
                        if sales_agent and sales_agent.factor_code:
                            factor_code = sales_agent.factor_code
                    except Exception as e:
                        logger.warning(f"Error al obtener factor_code del agente: {str(e)}")
            
            # Generamos el número de factura secuencial
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
        
        # 🔗 مکانیزم همگام‌سازی کارشناس فروش با مشتری
        # اگر unique_sales_agent تنظیم شده و مشتری موجود است،
        # کارشناس فروش را به لیست sales_agent های مشتری اضافه می‌کنیم
        if self.unique_sales_agent and self.customer:
            # بررسی اینکه آیا این کارشناس قبلاً در لیست sales_agent های مشتری هست یا نه
            if not self.customer.sales_agent.filter(id=self.unique_sales_agent.id).exists():
                self.customer.sales_agent.add(self.unique_sales_agent)
                logger.info(f"✅ کارشناس فروش {self.unique_sales_agent.name} به لیست کارشناسان مشتری {self.customer.name} اضافه شد")
        
        # اضافه کردن کاربر فعلی به عنوان کارشناس فروش خرید
        # این قسمت را در view هایی که خرید ایجاد می‌کنند استفاده می‌کنیم
        # و کاربر فعلی را مشخص می‌کنیم
        
        # نکته: دیگر کارشناس فروش مشتری به خرید اضافه نمی‌شود
        # sales_agents = self.customer.sales_agent.all()
        # for agent in sales_agents:
        #     self.sales_agent.add(agent)
        
        # بررسی اینکه آیا SMS ارسال شود
        has_non_admin = False
        if hasattr(self, 'sales_agent'):
            for agent in self.sales_agent.all():
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

        if self.state == 'PURCHASE_CLOSED':
            if self.extelaf_type == 'کسری':
                self.state = 'PAY_KASRI'
            elif self.extelaf_type == 'سرک':
                self.state = 'RECIEIVE_SARAK'
            if self.extelaf_weight == 0:
                self.state = 'FULLY_SETTLED'
            super().save(update_fields=['state'])

        # محاسبه خودکار amount_paid فقط در صورتی که مقدار تنظیم نشده باشد
        # یا در حالت‌های خاص که نیاز به بازمحاسبه داریم
        if not self.amount_paid or self.amount_paid == 0:
            if self.is_factored and self.delivered_weight and self.customer_price:
                self.amount_paid = self.customer_price * self.delivered_weight
                super().save(update_fields=['amount_paid'])
            elif not self.is_factored and self.order_weight and self.customer_price:
                self.amount_paid = self.customer_price * self.order_weight
                super().save(update_fields=['amount_paid'])

        from core.CustomerModel import CrmAccessNumbers
        if self.bazaargah_customer and self.bazaargah_phone_number:
            try: 
                # بررسی اینکه آیا این شماره قبلاً برای این مشتری ثبت شده یا نه
                existing_crm_number = CrmAccessNumbers.objects.filter(
                    customer=self.bazaargah_customer,
                    phone_number=self.bazaargah_phone_number
                ).exists()
                
                # اگر ثبت نشده باشد، اضافه کن
                if not existing_crm_number:
                    CrmAccessNumbers.objects.create(
                        customer=self.bazaargah_customer,
                        phone_number=self.bazaargah_phone_number
                    )
                    logger.info(f"✅ شماره تلفن {self.bazaargah_phone_number} به CRM مشتری {self.bazaargah_customer.name} اضافه شد")
                    
            except Exception as e:
                logger.warning(f"❌ خطا در اضافه کردن شماره تلفن به CRM: {str(e)}")

        if not self.state in ['INITIATED', 'SMS_SENT', 'PAYMENT_VERIFIED', 'ALLOCATION_APPROVED']:
            self.is_address_sent = '1'  # اصلاح: استفاده از string '1' به جای boolean True
            super().save(update_fields=['is_address_sent'])
            
        # تولید خودکار شناسه یکتا تحویل
        if not self.unique_delivery_id and self.invoice_id:
            self.generate_unique_delivery_id()
            
        # همگام‌سازی فیلدهای تحویل با فیلدهای موجود
        if not self.buyer_national_id and self.code_melli_tahvil:
            self.buyer_national_id = self.code_melli_tahvil
            
        if not self.delivery_receiver_name and self.buyer_name:
            self.delivery_receiver_name = self.buyer_name
            
        if not self.delivery_address and self.address:
            self.delivery_address = self.address

        self.set_purchase_factor_status()

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
                
    # متدهای کمکی برای فیلدهای جدید
    def generate_unique_delivery_id(self):
        """تولید شناسه یکتا برای تحویل"""
        if not self.unique_delivery_id:
            import uuid
            base_id = f"DEL-{self.invoice_id}-{uuid.uuid4().hex[:6].upper()}"
            # اطمینان از یکتا بودن
            while Purchase.objects.filter(unique_delivery_id=base_id).exists():
                base_id = f"DEL-{self.invoice_id}-{uuid.uuid4().hex[:6].upper()}"
            self.unique_delivery_id = base_id
            
    def get_delivery_info(self):
        """دریافت اطلاعات کامل تحویل"""
        return {
            'receiver_name': self.delivery_receiver_name or self.buyer_name,
            'delivery_address': self.delivery_address or self.address,
            'postal_code': self.delivery_postal_code,
            'national_id': self.buyer_national_id or self.code_melli_tahvil,
            'unique_id': self.unique_delivery_id,
            'vehicle_type': self.get_vehicle_type_display() if self.vehicle_type else 'نامشخص'
        }
        
    def get_barbary_info(self):
        """دریافت اطلاعات باربری"""
        barbary_info = {
            'confidential_number': self.barbary_confidential_number,
            'customer_number': self.barbary_customer_number,
            'barbary_name': self.cargo.barbary.name if (self.cargo and self.cargo.barbary) else None
        }
        return barbary_info
        
    def update_delivery_from_barnameh(self, barnameh):
        """بروزرسانی اطلاعات تحویل از بارنامه"""
        if hasattr(barnameh, 'receiver_name') and barnameh.receiver_name:
            self.delivery_receiver_name = barnameh.receiver_name
        if hasattr(barnameh, 'destination') and barnameh.destination:
            if not self.delivery_address:
                self.delivery_address = barnameh.destination
        if hasattr(barnameh, 'driver_name') and barnameh.driver_name:
            # اطلاعات راننده را می‌توان در توضیحات ذخیره کرد
            if not self.description:
                self.description = f"راننده: {barnameh.driver_name}"
            elif "راننده:" not in self.description:
                self.description += f" | راننده: {barnameh.driver_name}"

    def set_purchase_factor_status(self):
        from bki_barnameh.models.BarnamehModel import Barnameh
        barnamehs = Barnameh.objects.filter(purchase=self)
        
        if not barnamehs.exists():
            self.factor_status = 'not_factored'
            # استفاده از update_fields برای جلوگیری از حلقه بی‌نهایت
            super().save(update_fields=['factor_status'])
            return
        
        total_barnamehs = barnamehs.count()
        factored_barnamehs = barnamehs.filter(is_factored=True).count()
        
        if factored_barnamehs == total_barnamehs:
            # اگر همه بارنامه‌ها فاکتور صادر شده دارند
            self.factor_status = 'factored'
            super().save(update_fields=['factor_status'])
        elif factored_barnamehs > 0:
            # اگر حداقل یک بارنامه فاکتور صادر شده دارد اما نه همه
            self.factor_status = 'naghes_factored'
            super().save(update_fields=['factor_status'])
        else:
            # اگر هیچ بارنامه‌ای فاکتور صادر نشده دارد
            self.factor_status = 'not_factored'
            super().save(update_fields=['factor_status'])
                


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
    sms_sent = models.BooleanField("پیامک ارسال شد", default=False)
    sms_sent_at = models.DateTimeField("زمان ارسال پیامک", null=True, blank=True)
    
    class Meta:
        verbose_name = "تغییر وضعیت خرید"
        verbose_name_plural = "تغییرات وضعیت خرید"
        ordering = ['-changed_at']
        
    def __str__(self):
        return f"تغییر از {self.get_previous_state_display()} به {self.get_new_state_display()} در {self.changed_at}"

class ShenaseTakhsis(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='shenase_takhsis_set', verbose_name="خرید مرتبط", null=True, blank=True)
    purchase_number = models.CharField("شماره خرید", max_length=255, null=True, blank=True)
    code = models.CharField("شناسه تخصیص", max_length=255, unique=True)
    weight = models.PositiveIntegerField(verbose_name="وزن تخصیص", null=True, blank=True)
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.purchase and self.purchase_number:
            self.purchase = Purchase.objects.get(purchase_number=self.purchase_number)
        super().save(*args, **kwargs)

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
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='purchase_sales_agents', null=True, blank=True)
    sales_agent = models.ForeignKey(SalesAgent, on_delete=models.CASCADE, related_name='purchase_relations', null=True, blank=True)
    purchase_number = models.CharField("شماره خرید", max_length=255, null=True, blank=True)
    sales_agent_name = models.CharField("نام کارشناس فروش", max_length=255, null=True, blank=True)
    created_at = jmodels.jDateTimeField("تاریخ ثبت", auto_now_add=True)
    
    class Meta:
        verbose_name = "کارشناس فروش خرید"
        verbose_name_plural = "کارشناس فروش خریدها"

    def save(self, *args, **kwargs):
        if not self.purchase and self.purchase_number:
            self.purchase = Purchase.objects.get(purchase_number=self.purchase_number)
        if not self.sales_agent and self.sales_agent_name:
            self.sales_agent = SalesAgent.objects.get(name=self.sales_agent_name)
        super().save(*args, **kwargs)

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
