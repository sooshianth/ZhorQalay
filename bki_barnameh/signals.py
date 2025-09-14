from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from sms_api.apis import queue_sms
from sms_api.models import SmsTemplate
import logging
from .models.BarnamehModel import Barnameh
from jdatetime import date as jdate

# تلاش برای import pandas، اگر موجود نبود از روش جایگزین استفاده کن
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger('bki_barnameh_signals')

# دیکشنری برای ذخیره مقادیر قبلی is_sent_to_bki
_old_is_sent_to_bki_values = {}

@receiver(pre_save, sender=Barnameh)
def store_old_is_sent_to_bki(sender, instance, **kwargs):
    """
    ذخیره مقدار قبلی is_sent_to_bki قبل از ذخیره
    """
    if instance.pk:
        try:
            old_instance = Barnameh.objects.get(pk=instance.pk)
            _old_is_sent_to_bki_values[instance.pk] = old_instance.is_sent_to_bki
            logger.debug(f"Stored old is_sent_to_bki value for barnameh {instance.pk}: {old_instance.is_sent_to_bki}")
        except Barnameh.DoesNotExist:
            _old_is_sent_to_bki_values[instance.pk] = False
            logger.debug(f"Barnameh {instance.pk} not found, assuming old is_sent_to_bki = False")

def create_default_barnameh_template():
    """
    ایجاد قالب پیش‌فرض برای بارنامه در صورت عدم وجود
    """
    try:
        template, created = SmsTemplate.objects.get_or_create(
            status='BARNAMEH_CREATED',
            defaults={
                'name': 'قالب پیش‌فرض بارنامه جدید',
                'template_type': 'purchase',
                'content': '''{{customer_name}} عزیز؛
                بارنامه خرید {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} :
                شماره بارنامه: {{barnameh_number}}
                تاریخ بارنامه: {{barnameh_date}}
                شماره راننده: {{driver_phone}}
                نام راننده: {{driver_name}}
                ۰۲۱-۶۶۵۶۲۲۱۶ ☎️
                شرکت تامین نهاده سیمرغ''',
                'description': 'قالب پیش‌فرض برای اطلاع‌رسانی بارنامه جدید (ایجاد شده توسط سیگنال)',
                'is_active': True,
                'is_default': True
            }
        )
        if created:
            logger.info(f"✅ Created default SMS template for BARNAMEH_CREATED: {template.name}")
        return template
    except Exception as e:
        logger.error(f"❌ Error creating default barnameh template: {str(e)}")
        return None

@receiver(post_save, sender=Barnameh)
def send_sms_on_barnameh_bki_success(sender, instance, created, **kwargs):
    """
    ارسال پیامک به مشتری هنگام ارسال موفق بارنامه به بازارگاه
    این سیگنال فقط زمانی اجرا می‌شود که بارنامه با موفقیت به بازارگاه ارسال شده باشد
    """
    # لاگ اولیه برای تایید اجرای سیگنال
    logger.info(f"🚨 SIGNAL TRIGGERED: Barnameh {instance.id} post_save signal - created={created}, is_sent_to_bki={instance.is_sent_to_bki}, number={instance.number}")
    
    # بررسی شرایط ارسال پیامک:
    # فقط زمانی پیامک ارسال شود که بارنامه به بازارگاه ارسال شده باشد
    if not instance.is_sent_to_bki:
        logger.info(f"⏭️ Skipping SMS for barnameh {instance.id} - not sent to BKI yet (is_sent_to_bki={instance.is_sent_to_bki})")
        return
    
    # اگر این یک آپدیت است، بررسی کنیم که آیا is_sent_to_bki تازه تغییر کرده یا نه
    if not created:
        # بررسی تغییرات فیلد با استفاده از مقدار ذخیره شده در pre_save
        old_is_sent_to_bki = _old_is_sent_to_bki_values.get(instance.pk, False)
        
        # اگر قبلاً is_sent_to_bki برابر True بوده، پیامک ارسال نکن
        if old_is_sent_to_bki:
            logger.info(f"⏭️ Skipping SMS for barnameh {instance.id} - already was sent to BKI before this update (old_value={old_is_sent_to_bki}, new_value={instance.is_sent_to_bki})")
            # پاک کردن مقدار ذخیره شده
            _old_is_sent_to_bki_values.pop(instance.pk, None)
            return
        
        logger.info(f"🔄 Barnameh {instance.id} is_sent_to_bki changed from {old_is_sent_to_bki} to {instance.is_sent_to_bki}")
        
        # پاک کردن مقدار ذخیره شده
        _old_is_sent_to_bki_values.pop(instance.pk, None)
    
    logger.info(f"✅ Barnameh {instance.id} eligible for SMS - successfully sent to BKI, number={instance.number}, sent_at={instance.is_sent_to_bki_at}")
    
    # بررسی تاریخ بارنامه 
    # شرط: اگر تاریخ بارنامه 3 روز یا بیشتر قبل از امروز باشد (قدیمی)، پیامک ارسال نشود
    if instance.barnameh_date:
        today = jdate.today()
        # فقط اختلاف گذشته؛ تاریخ‌های آینده شامل نمی‌شود
        past_days = (today - instance.barnameh_date).days
        if past_days >= 3:
            logger.info(
                f"Barnameh {instance.id} is older than or equal to 3 days (past_days={past_days}), skipping SMS"
            )
            return
    
    # جمع‌آوری شماره‌های تلفن مشتری برای ارسال پیامک
    phone_numbers = []
    
    # اضافه کردن شماره‌های مشتری (از طریق Purchase)
    logger.info(f"🔍 Checking purchase association for barnameh {instance.id}: purchase={instance.purchase}")
    
    if instance.purchase and instance.purchase.customer:
        customer = instance.purchase.customer
        logger.info(f"✅ Found customer: {customer.name} (ID: {customer.id}) for barnameh {instance.id}")
        
        # بررسی تنظیمات SMS مشتری
        logger.info(f"📱 Customer SMS preference: {customer.sms_preference}")
        if customer.sms_preference:
            # استفاده از متد بهبود یافته get_all_phone_numbers که خودش تکرارها رو حذف می‌کنه
            customer_phones = customer.get_all_phone_numbers(instance.purchase, True)
            logger.info(f"📞 Found {len(customer_phones)} unique phone numbers for customer: {customer_phones}")
            phone_numbers.extend(customer_phones)
            
            # 🎯 اضافه کردن شماره تحویل از تخصیص (اگر موجود باشد)
            if instance.shenase_takhsis and instance.shenase_takhsis.tahvil_phone_number:
                allocation_phone = instance.shenase_takhsis.tahvil_phone_number.strip()
                if allocation_phone and allocation_phone not in phone_numbers:
                    phone_numbers.append(allocation_phone)
                    logger.info(f"📱 Added allocation delivery phone: {allocation_phone} for barnameh {instance.id}")
            
        else:
            logger.warning(f"❌ Customer SMS not sent for barnameh {instance.id}: SMS preference is disabled")
    else:
        if not instance.purchase:
            logger.warning(f"❌ No purchase associated with barnameh {instance.id}")
        elif not instance.purchase.customer:
            logger.warning(f"❌ Purchase {instance.purchase.id} has no customer for barnameh {instance.id}")

    # اگر هیچ شماره‌ای از Purchase پیدا نشد، تلاش کن با purchase_number آن را پیدا کنی
    if not phone_numbers and instance.purchase_number:
        logger.info(f"🔍 No phone numbers from purchase, trying to find purchase by number: {instance.purchase_number}")
        try:
            from core.PurchaseModel import Purchase
            purchase = Purchase.objects.get(purchase_number=instance.purchase_number)
            if purchase.customer and purchase.customer.sms_preference:
                customer_phones = purchase.customer.get_all_phone_numbers(purchase, True)
                logger.info(f"📞 Found {len(customer_phones)} unique phone numbers from purchase_number lookup")
                phone_numbers.extend(customer_phones)
                
                # 🎯 اضافه کردن شماره تحویل از تخصیص (اگر موجود باشد)
                if instance.shenase_takhsis and instance.shenase_takhsis.tahvil_phone_number:
                    allocation_phone = instance.shenase_takhsis.tahvil_phone_number.strip()
                    if allocation_phone and allocation_phone not in phone_numbers:
                        phone_numbers.append(allocation_phone)
                        logger.info(f"📱 Added allocation delivery phone from purchase lookup: {allocation_phone} for barnameh {instance.id}")
                
                # بروزرسانی ارتباط بارنامه با خرید
                if not instance.purchase:
                    instance.purchase = purchase
                    instance.save()
                    logger.info(f"✅ Updated barnameh {instance.id} with purchase {purchase.id}")
        except Purchase.DoesNotExist:
            logger.warning(f"❌ Purchase with number {instance.purchase_number} not found")
        except Exception as e:
            logger.error(f"❌ Error finding purchase by number: {str(e)}")
    
    # 🎯 اگر هنوز شماره‌ای پیدا نشد اما تخصیص موجود است، از شماره تحویل تخصیص استفاده کن
    if not phone_numbers and instance.shenase_takhsis and instance.shenase_takhsis.tahvil_phone_number:
        allocation_phone = instance.shenase_takhsis.tahvil_phone_number.strip()
        if allocation_phone:
            phone_numbers.append(allocation_phone)
            logger.info(f"📱 Using only allocation delivery phone: {allocation_phone} for barnameh {instance.id} (no customer phones found)")
    
    if not phone_numbers:
        logger.warning(f"❌ No phone numbers found for barnameh {instance.id}, will not send SMS")
        return

    try:
        # ساخت متن پیامک کوتاه و صرفه‌جویانه
        message = "بارنامه صادر شد:\n"
        
        # اضافه کردن اطلاعات اصلی بارنامه (فقط در صورت وجود)
        purchase_number = get_safe_value(instance.purchase.purchase_number if instance.purchase else None)
        if purchase_number:
            message += f"شماره خرید: {convert_to_persian_numbers(purchase_number)}\n"
        
        barnameh_number = get_safe_value(instance.number)
        if barnameh_number:
            message += f"شماره بارنامه: {convert_to_persian_numbers(barnameh_number)}\n"
        
        barnameh_serial = get_safe_value(instance.serial)
        if barnameh_serial:
            message += f"سریال: {convert_to_persian_numbers(barnameh_serial)}\n"
        
        # اضافه کردن تاریخ بارنامه
        if instance.barnameh_date:
            barnameh_date = convert_to_persian_numbers(instance.barnameh_date.strftime("%Y/%m/%d"))
            message += f"تاریخ: {barnameh_date}\n"
        
        # اضافه کردن اطلاعات راننده (فقط در صورت وجود)
        driver_name = get_safe_value(instance.driver_name)
        if driver_name:
            message += f"نام راننده: {driver_name}\n"
        
        driver_phone = get_safe_value(instance.driver_phone)
        if driver_phone:
            message += f"شماره راننده: {convert_to_persian_numbers(driver_phone)}\n"
        
        # اضافه کردن نام شرکت
        message += "تأمین نهاده سیمرغ\n"
        message += "☎ 021-66562216"
        
        logger.info(f"📝 Hardcoded SMS message created for barnameh {instance.id}")
        logger.debug(f"📄 SMS content: {message}")
        
        # ارسال پیامک به همه شماره‌ها
        success_count = 0
        for phone in phone_numbers:
            try:
                logger.info(f"🔄 Attempting to queue SMS for barnameh {instance.id} to {phone}")
                queue_sms(
                    number=phone,
                    message=message,
                    notification_type='custom',
                    purchase=instance.purchase  # در صورت وجود
                )
                success_count += 1
                logger.info(f"✅ Successfully queued SMS for barnameh {instance.id} to {phone}")
            except Exception as e:
                logger.error(f"❌ Error queuing SMS for {phone} (Barnameh ID: {instance.id}): {str(e)}")
        
        if success_count > 0:
            logger.info(f"🎉 Successfully queued SMS for barnameh {instance.id} sent to BKI to {success_count} numbers")
        else:
            logger.warning(f"⚠️ Failed to queue SMS for any numbers for barnameh {instance.id}")
    
    except Exception as e:
        logger.error(f"Error processing SMS for barnameh {instance.id} sent to BKI: {str(e)}")

def is_valid_value(value):
    """
    بررسی می‌کند که مقدار معتبر است یا نه (نه nan، نه None، نه خالی)
    """
    if value is None:
        return False
    
    # اگر pandas موجود است، از pd.isna استفاده کن
    if HAS_PANDAS:
        if pd.isna(value):
            return False
    
    # بررسی مقادیر خالی یا نامعتبر
    str_value = str(value).strip().lower()
    if str_value in ['', 'nan', 'none', 'نامشخص', 'null']:
        return False
    
    # بررسی float('nan') در صورت عدم وجود pandas
    if not HAS_PANDAS:
        try:
            import math
            if isinstance(value, float) and math.isnan(value):
                return False
        except (TypeError, ValueError):
            pass
    
    return True

def get_safe_value(value, default=""):
    """
    مقدار معتبر برمی‌گرداند یا در صورت نامعتبر بودن، مقدار پیش‌فرض
    """
    if is_valid_value(value):
        return str(value).strip()
    return default

def convert_to_persian_numbers(text):
    """
    تبدیل اعداد انگلیسی به فارسی برای صرفه‌جویی در هزینه‌های پیامک
    """
    if not text:
        return text
    
    # دیکشنری تبدیل اعداد انگلیسی به فارسی
    persian_numbers = {
        '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
        '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
    }
    
    # تبدیل متن به رشته
    text_str = str(text)
    
    # تبدیل اعداد
    for eng, per in persian_numbers.items():
        text_str = text_str.replace(eng, per)
    
    return text_str 