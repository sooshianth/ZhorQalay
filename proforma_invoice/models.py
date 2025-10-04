from django.db import models
from django_jalali.db import models as jmodels
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent
import jdatetime
import random
import string


class CompanyInfo(models.Model):
    """مدل اطلاعات شرکت برای صدور پیش فاکتور"""
    
    # اطلاعات شناسایی
    company_name = models.CharField(_("نام شرکت"), max_length=200, default="شرکت تامین نهاده سیمرغ")
    company_id_code = models.CharField(_("شناسه ملی شرکت"), max_length=20, blank=True, null=True)
    economic_code = models.CharField(_("کد اقتصادی"), max_length=20, blank=True, null=True)
    registration_number = models.CharField(_("شماره ثبت"), max_length=20, blank=True, null=True)
    
    # اطلاعات تماس
    phone_number = models.CharField(_("شماره تلفن"), max_length=50, blank=True, null=True)
    mobile_number = models.CharField(_("شماره موبایل"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("ایمیل"), blank=True, null=True)
    website = models.URLField(_("وب‌سایت"), blank=True, null=True)
    
    # آدرس و موقعیت
    address = models.TextField(_("آدرس کامل"), blank=True, null=True)
    postal_code = models.CharField(_("کد پستی"), max_length=20, blank=True, null=True)
    
    # اطلاعات مالی
    bank_name = models.CharField(_("نام بانک"), max_length=100, blank=True, null=True)
    account_number = models.CharField(_("شماره حساب"), max_length=50, blank=True, null=True)
    iban = models.CharField(_("شماره شبا"), max_length=50, blank=True, null=True, help_text="IR + 24 رقم")
    card_number = models.CharField(_("شماره کارت"), max_length=20, blank=True, null=True)
    
    # لوگو و امضا
    logo = models.ImageField(_("لوگوی شرکت"), upload_to='company_logo/', blank=True, null=True)
    signature_image = models.ImageField(_("تصویر امضا"), upload_to='company_signature/', blank=True, null=True)
    
    # ملاحظات پیش‌فرض
    default_notes = models.TextField(_("ملاحظات پیش‌فرض"), blank=True, null=True,
                                    help_text="این متن به صورت پیش‌فرض در تمام پیش فاکتورها نمایش داده می‌شود")
    
    # تنظیمات
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ بروزرسانی"), auto_now=True)
    
    class Meta:
        verbose_name = _("اطلاعات شرکت")
        verbose_name_plural = _("اطلاعات شرکت‌ها")
        
    def __str__(self):
        return self.company_name
    
    @classmethod
    def get_active_company(cls):
        """دریافت اطلاعات شرکت فعال"""
        return cls.objects.filter(is_active=True).first()


class ProformaInvoice(models.Model):
    """مدل پیش فاکتور"""
    
    UNIT_CHOICES = [
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
        ('bag', 'کیسه'),
    ]
    
    # شماره پیش فاکتور (سریال)
    invoice_number = models.CharField(_("شماره پیش فاکتور"), max_length=20, unique=True, editable=False)
    
    # اطلاعات مرتبط
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, 
                                related_name='proforma_invoices', 
                                verbose_name=_("مشتری"))
    sales_agent = models.ForeignKey(SalesAgent, on_delete=models.SET_NULL, 
                                   null=True, blank=True,
                                   related_name='proforma_invoices',
                                   verbose_name=_("کارشناس فروش"))
    company_info = models.ForeignKey(CompanyInfo, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    verbose_name=_("اطلاعات شرکت"))
    
    # اطلاعات محصول
    product = models.ForeignKey(CargoProduct, on_delete=models.SET_NULL,
                               null=True, blank=True,
                               verbose_name=_("محصول"))
    product_name = models.CharField(_("نام محصول"), max_length=200,
                                   help_text="در صورت خالی بودن از نام محصول استفاده می‌شود")
    product_description = models.TextField(_("توضیحات محصول"), blank=True, null=True)
    
    # مشخصات فروش
    quantity = models.DecimalField(_("مقدار"), max_digits=10, decimal_places=2,
                                  validators=[MinValueValidator(0)])
    unit = models.CharField(_("واحد"), max_length=10, choices=UNIT_CHOICES, default='kg')
    unit_price = models.DecimalField(_("قیمت واحد (ریال)"), max_digits=15, decimal_places=0,
                                    validators=[MinValueValidator(0)])
    
    # محاسبات خودکار
    total_price = models.DecimalField(_("قیمت کل (ریال)"), max_digits=15, decimal_places=0,
                                     editable=False, default=0)
    
    # تاریخ‌ها
    issue_date = jmodels.jDateField(_("تاریخ صدور"), auto_now_add=True)
    valid_until = jmodels.jDateField(_("تاریخ اعتبار"))
    
    # ملاحظات
    notes = models.TextField(_("ملاحظات"), blank=True, null=True)
    
    # وضعیت
    is_finalized = models.BooleanField(_("نهایی شده"), default=False)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ بروزرسانی"), auto_now=True)
    
    class Meta:
        verbose_name = _("پیش فاکتور")
        verbose_name_plural = _("پیش فاکتورها")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"پیش فاکتور {self.invoice_number} - {self.customer.name}"
    
    def save(self, *args, **kwargs):
        # تولید شماره پیش فاکتور
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        # محاسبه قیمت کل
        self.total_price = self.quantity * self.unit_price
        
        # تنظیم تاریخ اعتبار (یک روز بعد از تاریخ صدور)
        if not self.valid_until:
            today = jdatetime.date.today()
            self.valid_until = today + jdatetime.timedelta(days=1)
        
        # اگر نام محصول خالی است، از نام محصول مرتبط استفاده کن
        if not self.product_name and self.product:
            self.product_name = self.product.get_product_type_display()
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_invoice_number():
        """تولید شماره یکتای پیش فاکتور"""
        today = jdatetime.date.today()
        year = str(today.year)[2:]  # دو رقم آخر سال
        month = f"{today.month:02d}"
        day = f"{today.day:02d}"
        
        # شماره سریال روزانه
        today_invoices_count = ProformaInvoice.objects.filter(
            issue_date=today
        ).count()
        serial = f"{today_invoices_count + 1:03d}"
        
        # فرمت: PI-YYMMDD-XXX
        invoice_number = f"PI-{year}{month}{day}-{serial}"
        
        # اطمینان از یکتا بودن
        while ProformaInvoice.objects.filter(invoice_number=invoice_number).exists():
            random_suffix = ''.join(random.choices(string.digits, k=2))
            invoice_number = f"PI-{year}{month}{day}-{serial}{random_suffix}"
        
        return invoice_number
    
    def get_total_price_with_tax(self, tax_rate=0.09):
        """محاسبه قیمت با مالیات (پیش‌فرض 9%)"""
        return self.total_price * (1 + tax_rate)
    
    def get_formatted_quantity(self):
        """فرمت کردن مقدار با واحد"""
        unit_display = dict(self.UNIT_CHOICES).get(self.unit, self.unit)
        return f"{self.quantity:,} {unit_display}"
    
    def get_formatted_unit_price(self):
        """فرمت کردن قیمت واحد"""
        return f"{self.unit_price:,} ریال"
    
    def get_formatted_total_price(self):
        """فرمت کردن قیمت کل"""
        return f"{self.total_price:,} ریال"
