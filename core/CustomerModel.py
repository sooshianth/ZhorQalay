from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .SalesAgentModel import SalesAgent
from .CargoProductModel import CargoProduct
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger("core_customer")


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


PAYMENT_PREFERENCE_CHOICES = [
    ('cash', 'نقدی'),
    ('check', 'چک'),
    ('credit', 'اعتباری'),
    ('transfer', 'انتقال بانکی'),
    ('bazaargah', 'بازارگاه')
]

class ActivityField(models.Model):
    """Model representing field of activity"""
    code = models.CharField(_("کد"), max_length=50, choices=FIELD_OF_ACTIVITY, unique=True)
    
    class Meta:
        verbose_name = _("حیطه فعالیت")
        verbose_name_plural = _("حیطه های فعالیت")
    
    def __str__(self):
        return dict(FIELD_OF_ACTIVITY).get(self.code, self.code)

class ProductPreference(models.Model):
    """Model representing product preference"""
    code = models.CharField(_("کد"), max_length=50, choices=CargoProduct.PRODUCT_TYPES)
    
    class Meta:
        verbose_name = _("ترجیح کالایی")
        verbose_name_plural = _("ترجیحات کالایی")
    
    def __str__(self):
        return dict(CargoProduct.PRODUCT_TYPES).get(self.code, self.code)

class PaymentPreference(models.Model):
    """Model representing payment preference"""
    code = models.CharField(_("کد"), max_length=50, choices=PAYMENT_PREFERENCE_CHOICES, unique=True)
    
    class Meta:
        verbose_name = _("ترجیح پرداخت")
        verbose_name_plural = _("ترجیحات پرداخت")
    
    def __str__(self):
        return dict(PAYMENT_PREFERENCE_CHOICES).get(self.code, self.code)

class PhoneNumber(models.Model):
    number = models.CharField(_("شماره تلفن"), max_length=20)
    is_primary = models.BooleanField(_("شماره اصلی"), default=False)
    sms_enabled = models.BooleanField(_("ارسال پیامک"), default=True, help_text=_("آیا پیامک به این شماره ارسال شود؟"))
    description = models.CharField(_("توضیحات"), max_length=100, blank=True, null=True, help_text=_("توضیحات اختیاری برای این شماره تلفن"))
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='phone_numbers', verbose_name=_("مشتری"))
    
    class Meta:
        verbose_name = _("شماره تلفن")
        verbose_name_plural = _("شماره های تلفن")
    
    def __str__(self):
        return self.number
    
    def clean(self):
        # اطمینان از فرمت درست شماره تلفن
        self.number = self.number.strip()
        
        # Convert Persian digits to English digits if needed
        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        english_digits = "0123456789"
        translation_table = str.maketrans(persian_digits, english_digits)
        self.number = self.number.translate(translation_table)
        
        # پاکسازی شماره از کاراکترهای غیرعددی
        cleaned_number = ''.join(c for c in self.number if c.isdigit())
        
        # اگر عددی وجود نداشت، خطا بده
        if not cleaned_number:
            cleaned_number = self.number
            
        # Check for previously incorrectly stored numbers like 9000000000
        if cleaned_number == "9000000000" and self.number != "9000000000":
            # Don't modify the number, leave it as is
            pass
        else:
            # اگر با صفر شروع می‌شود، آن را حذف می‌کنیم
            if cleaned_number.startswith('0'):
                cleaned_number = cleaned_number[1:]
                
            # حذف کد کشور ایران اگر وجود داشت
            if cleaned_number.startswith('98'):
                cleaned_number = cleaned_number[2:]
            
            # توصیه‌ها به جای اعتبارسنجی اجباری
            if not cleaned_number.startswith('9'):
                # تنها هشدار بده، اما خطا نده
                logger.info(f'توجه: شماره تلفن {cleaned_number} با 9 شروع نمی‌شود، اما پذیرفته می‌شود.')
                
            if len(cleaned_number) != 10:
                # تنها هشدار بده، اما خطا نده
                logger.info(f'توجه: شماره تلفن {cleaned_number} دقیقاً 10 رقم نیست، اما پذیرفته می‌شود.')
            
            # ذخیره شماره پاکسازی شده
            self.number = cleaned_number
        
        # If this is being set as primary, make sure no other numbers for this customer are primary
        if self.is_primary:
            PhoneNumber.objects.filter(customer=self.customer, is_primary=True).exclude(id=self.id).update(is_primary=False)

    def save(self, *args, **kwargs):
        # Always clean before saving
        self.clean()
        super().save(*args, **kwargs)
        
        # If this is the primary number, update the customer's phone_number field
        if self.is_primary:
            self.customer.phone_number = self.number
            self.customer.save(update_fields=['phone_number'])

class Customer(models.Model):
    # phone_number field is no longer unique and will be deprecated
    phone_number = models.CharField(_("تلفن همراه (قدیمی)"), max_length=20, null=True, blank=True,
                                   help_text=_("این فیلد برای سازگاری با نسخه قبلی حفظ شده و به زودی حذف خواهد شد."))
    sales_agent = models.ManyToManyField(SalesAgent, verbose_name=_("کارشناسان فروش"), blank=True, related_name='customers')
    name = models.CharField(_("نام"), max_length=100, null=True, blank=True)
    city = models.CharField(_("شهر"), max_length=100, null=True, blank=True)
    whatsapp_preference = models.BooleanField(_("WhatsApp Preference"), default=False, help_text=_("تمایل به دریافت پیام واتساپ دارد؟"))
    # Changed from JSONField to ManyToMany relationship
    field_of_activity = models.ManyToManyField(
        ActivityField,
        verbose_name=_("حیطه فعالیت"),
        blank=True,
        related_name='customers'
    )
    # Changed from JSONField to ManyToMany relationship
    purchase_preferences = models.ManyToManyField(
        PaymentPreference,
        verbose_name=_("ترجیحات پرداخت"),
        blank=True,
        related_name='customers'
    )
    # Changed from JSONField to ManyToMany relationship
    product_preferences = models.ManyToManyField(
        ProductPreference,
        verbose_name=_("ترجیحات کالایی"),
        blank=True,
        related_name='customers'
    )
    contact_start_time = models.TimeField(_("زمان شروع تماس"), blank=True, null=True)
    contact_end_time = models.TimeField(_("زمان پایان تماس"), blank=True, null=True)
    social_media = models.CharField(_("شبکات اجتماعی"), max_length=255, blank=True, null=True,
        help_text=_("مثلا: ایتا و تلگرام، اینستاگرام: آیدیش")
    )
    added_description = models.TextField(_("توضیحات تکمیلی شناسنامه"), blank=True)
    sms_preference = models.BooleanField(_("SMS Preference"), default=True,
        help_text=_("تمایل به دریافت پیامک دارد؟")
    )
    day_of_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="روز هفته برای ارسال پیام (1-7 که 1=شنبه و 7=جمعه است)"
    )
    quota = models.CharField(_("سهمیه"),max_length=244, null=True, blank=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ثبت"), auto_now_add=True, null=True,    blank=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ بروزرسانی"), auto_now=True, null=True, blank=True)
    is_bazaargah_enjoyer = models.BooleanField(_("داخل بازارگاه؟"), default=True)
    is_favorite = models.BooleanField(_("مورد علاقه"), default=False)
    is_active = models.BooleanField(_("فعال"), default=True)
    is_blocked = models.BooleanField(_("مسدود"), default=False)
    

    class Meta:
        verbose_name = _("مشتری")
        verbose_name_plural = _("مشتریان")

    @staticmethod
    def get_customer_by_phone(phone_number):
        # Clean the phone number first
        if phone_number:
            phone_number = phone_number.strip()
            clean_number = ''.join(c for c in phone_number if c.isdigit())
            if clean_number.startswith('0'):
                clean_number = clean_number[1:]
        else:
            return None
            
        # Try to find a customer with this phone number in the new PhoneNumber model
        phone = PhoneNumber.objects.filter(number=clean_number).first()
        if phone:
            return phone.customer
        
        # Fallback to the old phone_number field
        return Customer.objects.filter(phone_number=clean_number).first()

    def get_primary_phone(self):
        primary = self.phone_numbers.filter(is_primary=True).first()
        if primary:
            return primary.number
        
        # Fallback to first phone or old phone_number
        first_phone = self.phone_numbers.first()
        if first_phone:
            return first_phone.number
        return self.phone_number or ''

    def get_all_phone_numbers(self, current_purchase=None, is_tahvil=False):
        """
        Returns a list of all unique phone numbers associated with this customer that have SMS enabled.
        Includes phone numbers from the PhoneNumber model (with sms_enabled=True),
        purchase phone numbers (bazaargah and tahvil), and if it exists,
        the legacy phone_number field.
        
        This method ensures no duplicate phone numbers are returned by:
        1. Normalizing all phone numbers to a standard format (removing prefixes)
        2. Using a set to automatically eliminate duplicates
        3. Filtering out invalid/empty numbers
        """
        if self.sms_preference == False:
            return []
        
        raw_numbers = []
        
        # Get SMS-enabled phone numbers from the PhoneNumber model
        for phone in self.phone_numbers.filter(sms_enabled=True):
            if phone.number:
                raw_numbers.append(phone.number)
        
        # Add phone numbers from purchases (bazaargah and tahvil)
        for purchase in self.purchases_made.all():
            if purchase.bazaargah_phone_number:
                raw_numbers.append(purchase.bazaargah_phone_number)

        # Add tahvil phone number if applicable
        if is_tahvil and current_purchase and current_purchase.tahvil_phone_number:
            raw_numbers.append(current_purchase.tahvil_phone_number)

        # Add the legacy phone number if it exists and customer has SMS preference enabled
        if self.phone_number and self.sms_preference:
            raw_numbers.append(self.phone_number)

        # Normalize and deduplicate phone numbers
        normalized_numbers = set()
        for phone in raw_numbers:
            if phone:
                # Convert to string and strip whitespace
                phone_str = str(phone).strip()
                
                # Skip empty or invalid numbers
                if not phone_str or phone_str.lower() in ['none', 'null', 'nan', '']:
                    continue
                
                # Convert Persian digits to English digits
                persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                english_digits = "0123456789"
                translation_table = str.maketrans(persian_digits, english_digits)
                phone_str = phone_str.translate(translation_table)
                
                # Remove non-digit characters except + at the beginning
                if phone_str.startswith('+'):
                    # Keep the + and remove other non-digits
                    cleaned = '+' + ''.join(c for c in phone_str[1:] if c.isdigit())
                else:
                    # Remove all non-digits
                    cleaned = ''.join(c for c in phone_str if c.isdigit())
                
                # Skip if no digits found
                if not any(c.isdigit() for c in cleaned):
                    continue
                
                # Normalize prefixes
                if cleaned.startswith('+98'):
                    cleaned = cleaned[3:]
                elif cleaned.startswith('0098'):
                    cleaned = cleaned[4:]
                elif cleaned.startswith('98') and len(cleaned) >= 12:  # 98 + حداقل 10 digits
                    cleaned = cleaned[2:]
                elif cleaned.startswith('0') and len(cleaned) >= 11:  # 0 + حداقل 10 digits
                    cleaned = cleaned[1:]
                
                # Final validation: should be 10 digits starting with 9
                if len(cleaned) == 10 and cleaned.startswith('9') and cleaned.isdigit():
                    normalized_numbers.add(cleaned)
                elif len(cleaned) >= 10:
                    # Try to extract a valid 10-digit number
                    for i in range(len(cleaned) - 9):
                        potential_number = cleaned[i:i+10]
                        if potential_number.startswith('9') and potential_number.isdigit():
                            normalized_numbers.add(potential_number)
                            break
        
        # Convert set back to list and sort for consistent ordering
        result = sorted(list(normalized_numbers))
        
        # Log for debugging (only if there are duplicates found)
        if len(raw_numbers) > len(result) and len(raw_numbers) > 1:
            logger.info(f"Customer {self.id}: Removed {len(raw_numbers) - len(result)} duplicate phone numbers")
            logger.debug(f"Raw numbers: {raw_numbers}")
            logger.debug(f"Final unique numbers: {result}")
        
        return result

    def get_tasks_by_time(self):
        return self.tasks.order_by('due_date')

    def get_calls_by_time(self):
        return self.calls.order_by('date')

    def get_purchases_by_time(self):
        return self.purchases_made.order_by('created_at')

    def get_purchases(self):
        return self.purchases.all()

    def get_calls(self):
        return self.calls.all()

    def get_tasks(self):
        return self.tasks.all()

    def get_name(self):
        return self.name

    def get_sales_agents(self):
        return self.sales_agent.all()

    def get_last_contact_datetime(self):
        return self.calls.last().date if self.calls.exists() else None

    def get_field_of_activity_display(self):
        """Returns a formatted string of the customer's field of activity"""
        if not self.field_of_activity.exists():
            return ""
            
        display_names = [activity.__str__() for activity in self.field_of_activity.all()]
        return "، ".join(display_names)
        
    def get_field_of_activity_list(self):
        """
        Returns the field_of_activity as a list of codes.
        """
        return [activity.code for activity in self.field_of_activity.all()]
        
    def set_field_of_activity_list(self, activity_codes):
        """
        Sets field_of_activity from a list of codes
        """
        if not activity_codes:
            self.field_of_activity.clear()
            return
        
        # Convert codes to ActivityField objects
        activity_fields = []
        for code in activity_codes:
            activity, created = ActivityField.objects.get_or_create(code=code)
            activity_fields.append(activity)
        
        # Set the relationship
        self.field_of_activity.set(activity_fields)
            
    def get_purchase_preferences_list(self):
        """
        Returns the purchase_preferences as a list of codes
        """
        return [pref.code for pref in self.purchase_preferences.all()]
        
    def set_purchase_preferences_list(self, preference_codes):
        """
        Sets purchase_preferences from a list of codes
        """
        if not preference_codes:
            self.purchase_preferences.clear()
            return
        
        # Convert codes to PaymentPreference objects
        payment_prefs = []
        for code in preference_codes:
            pref, created = PaymentPreference.objects.get_or_create(code=code)
            payment_prefs.append(pref)
        
        # Set the relationship
        self.purchase_preferences.set(payment_prefs)

    def get_product_preferences_list(self):
        """
        Returns the product_preferences as a list of codes
        """
        return [pref.code for pref in self.product_preferences.all()]
        
    def set_product_preferences_list(self, preference_codes):
        """
        Sets product_preferences from a list of codes
        """
        if not preference_codes:
            self.product_preferences.clear()
            return
        
        # Convert codes to ProductPreference objects
        product_prefs = []
        for code in preference_codes:
            pref, created = ProductPreference.objects.get_or_create(code=code)
            product_prefs.append(pref)
        
        # Set the relationship
        self.product_preferences.set(product_prefs)
            
    # Define properties for easy access
    field_of_activity_list = property(get_field_of_activity_list, set_field_of_activity_list)
    purchase_preferences_list = property(get_purchase_preferences_list, set_purchase_preferences_list)
    product_preferences_list = property(get_product_preferences_list, set_product_preferences_list)

    def __str__(self):
        primary_phone = self.get_primary_phone()
        name = self.name or 'بدون نام'
        return f"{primary_phone} {name}" if primary_phone else name
    
    def clean(self):
        if not self.name:
            raise ValidationError(_('نام را وارد کنید.'))
        
        # No need to validate phone_number here as it's now in the PhoneNumber model

    def change_sales_agent(self):
        """
        Change the sales agent for a customer.to next sales agent in the list
        """
        all_sales_agents = SalesAgent.objects.all()
        current_sales_agents = self.sales_agent.all()
        if not current_sales_agents:
            return None
        if SalesAgent.objects.get(user__username='Ms_Sadri') in current_sales_agents:
            next_sales_agent = SalesAgent.objects.get(user__username='Ms_Sadri')
        else:
            next_sales_agent = all_sales_agents.next()
        self.sales_agent.set([next_sales_agent])
        self.save()

    def change_sales_agents_after_two_months_of_no_purchase(self):
        """
        Change the sales agent for a customer after two months of no purchase.
        """
        if self.purchases_made.count() == 0:
            return None
        
        last_purchase = self.purchases_made.order_by('-created_at').first()
        if last_purchase.created_at < timezone.now() - timedelta(days=60):
            return None
        else:
            self.change_sales_agent()

    def get_purchase_phone_numbers(self):
        """
        Returns a list of unique phone numbers from customer's purchases.
        Includes bazaargah_phone_number and tahvil_phone_number from Purchase model.
        Removes duplicates while keeping the first occurrence.
        """
        phone_numbers = {}  # Use dict to keep track of first occurrence
        result = []
        
        # Get phone numbers from purchases
        for purchase in self.purchases_made.all():
            if purchase.bazaargah_phone_number:
                phone_key = ('بازارگاه', purchase.bazaargah_phone_number)
                if phone_key not in phone_numbers:
                    phone_numbers[phone_key] = True
                    result.append(('بازارگاه', purchase.bazaargah_phone_number, purchase.purchase_number))
                    
            if purchase.tahvil_phone_number:
                phone_key = ('تحویل', purchase.tahvil_phone_number)
                if phone_key not in phone_numbers:
                    phone_numbers[phone_key] = True
                    result.append(('تحویل', purchase.tahvil_phone_number, purchase.purchase_number))
        
        return result
    

class CrmAccessNumbers(models.Model):
    phone_number = models.CharField(max_length=12, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='crm_access_numbers', null=True, blank=True)

    def __str__(self) -> str:
        return f"شماره تلفن {self.phone_number} برای مشتری {self.customer} در سی‌آرام مجاز است"

    class Meta:
        db_table = ''
        managed = True
        verbose_name = 'شماره های مجاز در CRM'
        verbose_name_plural = 'شماره های مجاز در CRM'