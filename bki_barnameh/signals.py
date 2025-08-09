from django.db.models.signals import post_save
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
def send_sms_on_barnameh_create(sender, instance, created, **kwargs):
    """
    ارسال پیامک به مشتری هنگام ایجاد یا بروزرسانی بارنامه از اکسل
    """
    # لاگ اولیه برای تایید اجرای سیگنال
    logger.info(f"🚨 SIGNAL TRIGGERED: Barnameh {instance.id} post_save signal - created={created}, number={instance.number}, is_created_by_excel={getattr(instance, 'is_created_by_excel', False)}")
    
    # بررسی شرایط ارسال پیامک:
    # 1. بارنامه جدید ایجاد شده باشد (created=True)
    # 2. یا بارنامه از طریق اکسل ایجاد/بروزرسانی شده باشد (is_created_by_excel=True)
    should_send_sms = created or getattr(instance, 'is_created_by_excel', False)
    
    if not should_send_sms:
        logger.info(f"⏭️ Skipping SMS for barnameh {instance.id} - not eligible (created={created}, is_created_by_excel={getattr(instance, 'is_created_by_excel', False)})")
        return
    
    logger.info(f"✅ Barnameh {instance.id} eligible for SMS - created={created}, is_created_by_excel={getattr(instance, 'is_created_by_excel', False)}, number={instance.number}")
    
    # بررسی تاریخ بارنامه - فقط برای بارنامه‌های معمولی (نه آپلود شده از اکسل)
    # بارنامه‌های آپلود شده از اکسل معمولاً داده‌های تاریخی هستند و باید اطلاع‌رسانی شوند
    is_excel_upload = getattr(instance, 'is_created_by_excel', False)
    if instance.barnameh_date and not is_excel_upload:
        today = jdate.today()
        date_diff = abs((instance.barnameh_date - today).days)
        if date_diff > 2:
            logger.info(f"Barnameh {instance.id} date is more than 2 days away from today ({date_diff} days), skipping SMS (not Excel upload)")
            return
    
    # برای بارنامه‌های آپلود شده از اکسل، محدودیت تاریخی اعمال نمی‌شود
    if is_excel_upload:
        logger.info(f"📊 Excel upload detected for barnameh {instance.id} - bypassing date restriction")
    
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
                # بروزرسانی ارتباط بارنامه با خرید
                if not instance.purchase:
                    instance.purchase = purchase
                    instance.save()
                    logger.info(f"✅ Updated barnameh {instance.id} with purchase {purchase.id}")
        except Purchase.DoesNotExist:
            logger.warning(f"❌ Purchase with number {instance.purchase_number} not found")
        except Exception as e:
            logger.error(f"❌ Error finding purchase by number: {str(e)}")
    
    if not phone_numbers:
        logger.warning(f"❌ No phone numbers found for barnameh {instance.id}, will not send SMS")
        return

    try:
        # ساخت متن پیامک هاردکد شده
        message = "مشتری گرامی"
        
        # اضافه کردن اطلاعات اصلی بارنامه
        purchase_number = get_safe_value(instance.purchase.purchase_number if instance.purchase else None, "نامشخص")
        shenase_takhsis = get_safe_value(instance.shenase_takhsis_code, "نامشخص")
        barnameh_number = get_safe_value(instance.number, "نامشخص")
        barnameh_serial = get_safe_value(instance.serial, "نامشخص")
        barnameh_weight = get_safe_value(instance.tonnage, "نامشخص")
        
        message += f" بارنامه خرید {purchase_number} با شناسه تخصیص {shenase_takhsis} به شماره بارنامه {barnameh_number} و سریال {barnameh_serial} به وزن {barnameh_weight} صادر گردید."
        
        # اضافه کردن اطلاعات اختیاری (راننده، ماشین و ...)
        optional_info = []
        
        driver_name = get_safe_value(instance.driver_name)
        if driver_name:
            optional_info.append(f"نام راننده: {driver_name}")
        
        driver_phone = get_safe_value(instance.driver_phone)
        if driver_phone:
            optional_info.append(f"شماره راننده: {driver_phone}")
        
        vehicle_plate = get_safe_value(instance.vehicle_plate)
        if vehicle_plate:
            optional_info.append(f"پلاک خودرو: {vehicle_plate}")
        
        receiver_name = get_safe_value(instance.receiver_name)
        if receiver_name:
            optional_info.append(f"نام گیرنده: {receiver_name}")
        
        destination = get_safe_value(instance.destination)
        if destination:
            optional_info.append(f"مقصد: {destination}")
        
        # اگر اطلاعات اضافی موجود بود، آنها را اضافه کن
        if optional_info:
            message += "\n" + "\n".join(optional_info)
        
        # اضافه کردن اطلاعات تماس شرکت
        message += "\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ"
        
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
            logger.info(f"🎉 Successfully queued SMS for new barnameh {instance.id} to {success_count} numbers")
            
            # بعد از ارسال موفق پیامک، فیلد is_created_by_excel را False کن تا از ارسال تکراری جلوگیری شود
            if getattr(instance, 'is_created_by_excel', False):
                instance.is_created_by_excel = False
                instance.save(update_fields=['is_created_by_excel'])
                logger.info(f"🔄 Reset is_created_by_excel flag for barnameh {instance.id} after successful SMS")
        else:
            logger.warning(f"⚠️ Failed to queue SMS for any numbers for barnameh {instance.id}")
    
    except Exception as e:
        logger.error(f"Error processing SMS for new barnameh {instance.id}: {str(e)}")

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