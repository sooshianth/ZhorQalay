from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from core._models import Purchase, Task, SalesAgent
from django.db import models
from sms_api.apis import queue_sms, send_purchase_status_notification
from sms_api.models import SmsTemplate
import logging
from core.PurchaseModel import PurchaseStateChange

logger = logging.getLogger("core_zignals")


@receiver(post_save, sender=Purchase, dispatch_uid="create_task_for_purchase")
def create_task_for_purchase(sender, instance, created, **kwargs):
    if created:  # فقط اگر Purchase جدید ایجاد شده باشد
        # ایجاد تسک برای ۱۵ دقیقه بعد
        due_date = timezone.now() + timedelta(minutes=15)
        
        # توضیحات تسک
        task_description = f"پیگیری پیامک ارسال شده برای مشتری - کوتاژ {instance.cargo if instance.cargo else 'بدون کوتاژ'}"
        
        # ایجاد تسک
        # چک کردن اینکه آیا کارشناسان فروش مشتری فقط ادمین‌ها هستند یا نه
        sales_agents = instance.customer.sales_agent.all()
        has_non_admin = False
        for agent in sales_agents:
            if not agent.user.is_superuser:
                has_non_admin = True
                break
        
        if has_non_admin:
            Task.objects.create(
                description=task_description,
                customer=instance.customer,  # مشتری مرتبط با خرید
                purchase=instance,  # خرید مرتبط با تسک
                due_date=due_date,  # زمان انجام تسک (۱۵ دقیقه بعد)
                status=False  # تسک به‌صورت پیش‌فرض انجام نشده است
            )

# سیگنال جدید برای ارسال پیامک هنگام ایجاد خرید جدید
@receiver(post_save, sender=Purchase, dispatch_uid="send_sms_on_purchase_create")
def send_sms_on_purchase_create(sender, instance, created, **kwargs):
    """
    ارسال پیامک به مشتری هنگام ایجاد خرید جدید
    فقط برای خریدهای جدید اجرا می‌شود
    """
    if not created:  # فقط برای خریدهای جدید
        return
        
    logger.debug(f"New purchase created: {instance.id}, checking SMS conditions")
    
    # بررسی شرایط اولیه
    if not _should_send_sms(instance):
        return
    
    # مشاهده وضعیت فعلی خرید
    current_state = instance.state
    logger.info(f"Purchase {instance.id} current state: {current_state}")
    
    try:
        # ارسال پیامک برای وضعیت فعلی
        result = _send_sms_for_state_change(instance, 'INITIATED', current_state, "ارسال پیامک خودکار برای خرید جدید")
        
        if result:
            logger.info(f"Successfully sent SMS for new purchase {instance.id}")
        else:
            logger.warning(f"Failed to send SMS for new purchase {instance.id}")
    
    except Exception as e:
        logger.warning(f"Error processing SMS for new purchase {instance.id}: {str(e)}")


def _should_send_sms(instance):
    """
    بررسی اینکه آیا باید برای این خرید پیامک ارسال شود یا نه
    """
    # اگر مشتری وجود ندارد یا تنظیمات sms_preference غیرفعال است، پیامک ارسال نمی‌شود
    if not instance.customer or not instance.customer.sms_preference:
        logger.info(f"SMS not sent for purchase {instance.id}: Customer does not exist or SMS preference is disabled")
        return False
    
    # فقط برای خریدهایی که تنظیم send_cottage_sms آنها فعال است
    if not instance.send_cottage_sms:
        logger.info(f"SMS not sent for purchase {instance.id}: send_cottage_sms is disabled")
        return False
    
    return True


def _send_sms_for_state_change(purchase, previous_state, new_state, notes="تغییر وضعیت توسط سیستم"):
    """
    ارسال پیامک برای تغییر وضعیت خرید
    """
    # یافتن قالب پیام برای وضعیت جدید
    template = SmsTemplate.objects.filter(status=new_state, is_active=True).first()
    
    if not template:
        logger.info(f"No active SMS template found for state {new_state} (Purchase ID: {purchase.id})")
        return False
        
    # پردازش قالب پیام با استفاده از تابع send_purchase_status_notification
    result = send_purchase_status_notification(purchase, status=new_state)
    
    if result:
        # ایجاد رکورد تغییر وضعیت
        PurchaseStateChange.objects.create(
            purchase=purchase,
            previous_state=previous_state,
            new_state=new_state,
            sms_sent=True,
            sms_sent_at=timezone.now(),
            notes=notes
        )
        return True
    
    return False


@receiver(post_save, sender=PurchaseStateChange, dispatch_uid="send_sms_on_state_change")
def send_sms_on_state_change(sender, instance, created, **kwargs):
    """
    ارسال پیامک به مشتری هنگام تغییر وضعیت خرید
    این سیگنال فقط برای رکوردهای PurchaseStateChange که از طریق API یا سیستم ایجاد می‌شوند اجرا می‌شود
    """
    if not created:  # فقط برای رکوردهای جدید تغییر وضعیت
        logger.debug("Ignoring duplicate state change")
        return
    
    # بررسی اینکه تغییر وضعیت تازه است (کمتر از 1 روز)
    if instance.changed_at:
        time_diff = timezone.now() - instance.changed_at
        if time_diff.days >= 1:
            logger.info(f"State change is older than 1 day, skipping SMS for purchase {instance.purchase.id}")
            return
    
    logger.debug(f"Processing state change to {instance.new_state} for purchase {instance.purchase.id}")

    # اگر پیامک قبلا ارسال شده، دیگر ارسال نکن
    if instance.sms_sent:
        logger.info(f"SMS already sent for state change to {instance.new_state} for purchase {instance.purchase.id}")
        return
    
    purchase = instance.purchase
    new_state = instance.new_state
    
    # بررسی شرایط اولیه
    if not _should_send_sms(purchase):
        return
    
    try:
        # ارسال پیامک با استفاده از تابع موجود - استفاده از new_state به جای purchase.state
        result = send_purchase_status_notification(purchase, status=new_state)
        
        if result:
            logger.info(f"Successfully queued SMS for state change to {new_state} for purchase {purchase.id}")
            
            # آپدیت فیلد sms_sent در رکورد تغییر وضعیت
            instance.sms_sent = True
            instance.sms_sent_at = timezone.now()
            instance.save(update_fields=['sms_sent', 'sms_sent_at'])
        else:
            logger.warning(f"Failed to send SMS for state change to {new_state} for purchase {purchase.id}")
    
    except Exception as e:
        logger.warning(f"Error processing SMS for state change (Purchase ID: {purchase.id}): {str(e)}")


# سیگنال برای تشخیص تغییر مستقیم وضعیت در مدل Purchase
@receiver(pre_save, sender=Purchase, dispatch_uid="track_purchase_state_change")
def track_purchase_state_change(sender, instance, **kwargs):
    """
    ردیابی تغییرات وضعیت خرید قبل از ذخیره
    """
    if instance.pk:  # فقط برای آپدیت، نه برای ایجاد
        try:
            # دریافت وضعیت قبلی از دیتابیس
            old_instance = Purchase.objects.get(pk=instance.pk)
            instance._old_state = old_instance.state
        except Purchase.DoesNotExist:
            instance._old_state = None
    else:
        instance._old_state = None


@receiver(post_save, sender=Purchase, dispatch_uid="handle_direct_purchase_state_change")
def handle_direct_purchase_state_change(sender, instance, created, **kwargs):
    """
    مدیریت تغییر مستقیم وضعیت خرید (بدون استفاده از change_state)
    """
    if created:
        return  # برای خریدهای جدید کاری نکن
    
    # بررسی اینکه آیا وضعیت تغییر کرده
    old_state = getattr(instance, '_old_state', None)
    current_state = instance.state
    
    if old_state and old_state != current_state:
        logger.info(f"🔄 تغییر مستقیم وضعیت خرید {instance.purchase_number}: {old_state} → {current_state}")
        
        # بررسی اینکه آیا رکورد PurchaseStateChange برای این تغییر وجود دارد
        recent_state_change = PurchaseStateChange.objects.filter(
            purchase=instance,
            previous_state=old_state,
            new_state=current_state,
            changed_at__gte=timezone.now() - timedelta(minutes=5)
        ).exists()
        
        if not recent_state_change:
            # ایجاد رکورد تغییر وضعیت برای تریگر کردن سیگنال پیامک
            logger.info(f"📝 ایجاد رکورد تغییر وضعیت برای تغییر مستقیم: {old_state} → {current_state}")
            PurchaseStateChange.objects.create(
                purchase=instance,
                previous_state=old_state,
                new_state=current_state,
                notes='تغییر مستقیم وضعیت توسط سیستم یا API'
            )
        else:
            logger.debug(f"✅ رکورد تغییر وضعیت برای خرید {instance.purchase_number} قبلاً موجود است")