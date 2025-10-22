from django.db import models
from django_jalali.db import models as jmodels
from django.utils import timezone
from core.SalesAgentModel import SalesAgent

class BasePurchase(models.Model):

    FIELD_OF_ACTIVITY = [
    ('chicken', 'مرغدار'),
    ('livestock', 'دامدار'),
    ('factory', 'کارخانه خوراک'),
    ('fish', 'پرورش آبزیان'),
    ('corporation', 'تعاونی'),
    ('association', 'اتحادیه'),
    ('dealer', 'دلال'),
    ('aggressive', 'مزاحم'),
    ('other', 'سایر')
    ]

    PURCHASE_TYPE_CHOICES = [
        ('bazaargah', 'بازارگاه'),
        ('non_bazaargah', 'خارج از بازارگاه')
    ]

    #اطلاعات کلی
    id = models.AutoField(primary_key=True)
    customer = models.ForeignKey('core.Customer', on_delete=models.CASCADE, verbose_name='مشتری', null=True, blank=True)
    unique_sales_agent_code = models.CharField("کد کارشناس فروش", max_length=50, blank=True, null=True)
    unique_sales_agent = models.ForeignKey(SalesAgent, on_delete=models.SET_NULL, verbose_name="کارشناس فروش", null=True, blank=True, related_name='non_unique_sales_agent_purchases')
    description = models.TextField(verbose_name='توضیحات', null=True, blank=True)
    amount_paid = models.PositiveBigIntegerField("مبلغ پرداختی(ریال)", blank=True, null=True)
    total_weight = models.PositiveIntegerField("وزن کل (کیلوگرم)", default=0, null=True, blank=True)
    type = models.CharField("نوع خرید", max_length=25, default='bazaargah', choices=PURCHASE_TYPE_CHOICES)
    created_at = jmodels.jDateTimeField("تاریخ ثبت", default=timezone.now)
    updated_at  = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True, blank=True, null=True)
    closed_at = jmodels.jDateTimeField("تاریخ بسته شدن خرید", null=True, blank=True)

    #قیمت
    company_price = models.PositiveIntegerField("فی خرید(ریال)", default=0)
    customer_price = models.PositiveIntegerField("فی فروش(ریال)", default=0)

    # اطلاعات خریدار و تحویل 
    address = models.TextField("آدرس خریدار", blank=True, null=True)
    buyer_name = models.CharField("نام خریدار", max_length=255, blank=True, null=True)
    buyer_postal_code = models.CharField("کد پستی خریدار", max_length=10, blank=True, null=True)
    buyer_national_id = models.CharField("شناسه ملی خریدار", max_length=20, blank=True, null=True)
    buyer_user_type = models.CharField("نوع کاربری خریدار", max_length=20, choices=FIELD_OF_ACTIVITY, blank=True, null=True)
    tahvil_phone_number = models.CharField("شماره تلفن تحویل", max_length=15, blank=True, null=True)
    code_melli_tahvil = models.CharField("کد ملی تحویل", max_length=255, blank=True, null=True)
    delivery_address = models.TextField("آدرس تحویل", blank=True, null=True)
    delivery_postal_code = models.CharField("کد پستی تحویل", max_length=10, blank=True, null=True)
    delivery_receiver_name = models.CharField("نام تحویل گیرنده", max_length=255, blank=True, null=True)

    barbary_confidential_number = models.CharField("شماره باربری محرمانه", max_length=50, blank=True, null=True, 
                                                  help_text="شماره محرمانه باربری برای ادمین یا مالی  ")
    barbary_customer_number = models.CharField("شماره باربری مشتری", max_length=50, blank=True, null=True,
                                             help_text="شماره ارائه شده به مشتری از طرف باربری")
    VEHICLE_TYPE_CHOICES = [
        ('trailer', 'تریلی'),
        ('single', 'تک'),
        ('double', 'جفت'),
    ]
    vehicle_type = models.CharField("نوع خودرو حمل", max_length=20, choices=VEHICLE_TYPE_CHOICES,blank=True, null=True)

    class Meta:
        abstract = True