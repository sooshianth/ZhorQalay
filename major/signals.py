from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from .models.NonBazargahPurchase import NonBazargahPurchase
from .models.Invoice import Invoice
from .models.InvoiceItem import InvoiceItem
from .models.Hazinah import Hazinah

logger = logging.getLogger('major_signals')


@receiver(post_save, sender=NonBazargahPurchase)
def create_invoices_for_closed_purchase(sender, instance, created, **kwargs):
    """
    ایجاد خودکار فاکتور هزینه برای هر بارنامه هنگام بستن خرید خارج بازارگاه
    """
    # فقط وقتی که خرید بسته شده باشد (state = 'purchase_closed')
    if instance.state != 'purchase_closed':
        return
    
    try:
        # دریافت تمام بارنامه‌های مرتبط با این خرید
        barnamehs = instance.get_all_barnamehs()
        
        if not barnamehs:
            logger.warning(f"هیچ بارنامه‌ای برای خرید {instance.id} یافت نشد")
            return
        
        logger.info(f"شروع ایجاد فاکتور برای {len(barnamehs)} بارنامه خرید {instance.id}")
        
        for barnameh in barnamehs:
            # بررسی اینکه آیا قبلاً فاکتور ایجاد شده یا نه
            if Invoice.objects.filter(income=barnameh).exists():
                logger.info(f"فاکتور برای بارنامه {barnameh.id} قبلاً ایجاد شده است")
                continue
            
            # محاسبه وزن خالص بارنامه
            net_weight = None
            if barnameh.loaded_vehicle_weight and barnameh.empty_vehicle_weight:
                net_weight = float(barnameh.loaded_vehicle_weight) - float(barnameh.empty_vehicle_weight)
            
            # اگر وزن خالص موجود نباشد، از وزن نهایی تحویل استفاده کن
            if not net_weight and barnameh.final_delivered_weight:
                net_weight = float(barnameh.final_delivered_weight)
            
            # اگر هنوز وزن موجود نباشد، از وزن بارنامه استفاده کن
            if not net_weight and barnameh.tonnage:
                net_weight = float(barnameh.tonnage) * 1000  # تبدیل تن به کیلوگرم
            
            if not net_weight:
                logger.warning(f"وزن قابل محاسبه برای بارنامه {barnameh.id} یافت نشد")
                continue
            
            # دریافت فی خرید از خرید
            company_price = instance.company_price or 0
            
            # محاسبه مبلغ کل
            total_amount = int(net_weight * company_price)
            
            # ایجاد فاکتور هزینه
            invoice = Invoice.objects.create(
                type='Income',
                income=barnameh,
                issue_date=timezone.now().date(),
                invoice_id=f"{instance.purchase_number or instance.id}{barnameh.number or barnameh.id}",
                description=f"فاکتور برای بارنامه {barnameh.number or barnameh.id} - خرید {instance.purchase_number or instance.id}",
                customer=instance.customer
            )
            
            # ایجاد آیتم فاکتور
            InvoiceItem.objects.create(
                invoice=invoice,
                product_type='NonBazargah',
                non_bazargah_product=instance.product,
                price=company_price,
                amount=int(net_weight)
            )
            
            logger.info(f"فاکتور {invoice.invoice_id} برای بارنامه {barnameh.id} ایجاد شد - وزن: {net_weight} کیلوگرم، مبلغ: {total_amount:,} ریال")
        
        logger.info(f"تمام فاکتورهای خرید {instance.id} با موفقیت ایجاد شدند")
        
    except Exception as e:
        logger.error(f"خطا در ایجاد فاکتور برای خرید {instance.id}: {str(e)}")
        # در صورت خطا، لاگ کنید اما برنامه را متوقف نکنید


# --- SMS integration for NonBazargahPurchase ---
from sms_api.apis import send_purchase_status_notification, send_purchase_aware_notification
from sms_api.models import SmsConfig
from django.db.models.signals import pre_save
from sms_api.models import SmsQueue


@receiver(post_save, sender=NonBazargahPurchase, dispatch_uid="send_non_bazargah_purchase_aware")
def send_non_bazargah_purchase_aware(sender, instance, created, **kwargs):
    """
    هنگام ایجاد خرید خارج بازارگاه، در صورت فعال بودن تنظیمات، پیامک اطلاع‌رسانی مدیریت ارسال شود
    """
    if not created:
        return

    try:
        # send_purchase_aware_notification (management notification) should only be sent when enabled
        if SmsConfig.is_purchase_aware_enabled():
            try:
                result = send_purchase_aware_notification(instance)
                if result:
                    logger.info(f"Purchase aware SMS sent for NonBazargahPurchase {instance.id}")
                else:
                    logger.debug(f"No purchase aware SMS sent for NonBazargahPurchase {instance.id}")
            except Exception as e:
                logger.exception(f"Error sending purchase aware SMS for NonBazargahPurchase {instance.id}: {e}")
    except Exception as e:
        logger.exception(f"Error in management purchase aware flow for NonBazargahPurchase {instance.id}: {e}")

    # Additionally, always attempt to send the customer-facing initial SMS using non_bazargah templates
    try:
        if created and _should_send_non_bazargah_sms(instance):
            _send_sms_for_non_bazargah_state_change(instance, previous_state=None, new_state=instance.state, notes="ارسال پیامک هنگام ثبت خرید خارج بازارگاه")
    except Exception as e:
        logger.exception(f"Error sending initial non-bazargah SMS for {instance.id}: {e}")


def _should_send_non_bazargah_sms(instance):
    """Check whether we should send SMS for this NonBazargahPurchase (customer preference + optional flags)."""
    if not instance.customer or not getattr(instance.customer, 'sms_preference', False):
        logger.info(f"SMS not sent for NonBazargahPurchase {instance.id}: no customer or sms preference disabled")
        return False
    # if model has send_cottage_sms-like flag, respect it
    if hasattr(instance, 'send_cottage_sms') and not getattr(instance, 'send_cottage_sms'):
        logger.info(f"SMS not sent for NonBazargahPurchase {instance.id}: send_cottage_sms disabled")
        return False
    return True


def _send_sms_for_non_bazargah_state_change(instance, previous_state, new_state, notes="تغییر وضعیت توسط سیستم"):
    """Render non_bazargah template for the given state and queue SMSs to the customer.

    Avoid duplicate queuing by checking SmsQueue for existing entries with same purchase and notification_type.
    """
    try:
        # Check template exists
        from sms_api import apis as sms_apis
        # Try to find a template specifically for non_bazargah_status
        template = sms_apis.SmsTemplate.objects.filter(non_bazargah_status=new_state, is_active=True).first()
        if not template:
            # fallback: any template with that non_bazargah_status
            template = sms_apis.SmsTemplate.objects.filter(non_bazargah_status=new_state).first()
        # try uppercased (in case templates were created with uppercase values similar to Purchase statuses)
        if not template:
            template = sms_apis.SmsTemplate.objects.filter(non_bazargah_status=new_state.upper(), is_active=True).first()
        if not template:
            template = sms_apis.SmsTemplate.objects.filter(status=new_state.upper(), is_active=True).first()
        if not template:
            template = sms_apis.SmsTemplate.objects.filter(status=new_state, is_active=True).first()
        if not template:
            logger.info(f"No non_bazargah SMS template for state {new_state} (NonBazargahPurchase {instance.id})")
            # still attempt to render via render_template fallbacks below; don't return yet
            template = None

        # Duplicate protection: SmsQueue.purchase is a FK to core.Purchase, so we can't assign NonBazargahPurchase to it.
        # Instead check for queued messages with same notification_type and containing this purchase_number in the message.
        purchase_number = str(instance.purchase_number) if instance.purchase_number else str(instance.id)
        exists = SmsQueue.objects.filter(notification_type=new_state, purchase__isnull=True, message__icontains=purchase_number).exists()
        if exists:
            logger.info(f"SMS already queued for NonBazargahPurchase {instance.id} state {new_state}")
            return False

        # Build context
        context = {
            'customer': instance.customer,
            'purchase': instance,
            'customer_name': instance.customer.name if instance.customer else '',
            'purchase_number': instance.purchase_number or '',
            'invoice_id': getattr(instance, 'invoice_id', '') or '',
            'order_weight': getattr(instance, 'quantity', 0) or 0,
            'customer_price': getattr(instance, 'customer_price', 0),
            'amount_paid': getattr(instance, 'amount_paid', 0) or 0,
        }

        message = sms_apis.render_template(new_state, context, template_field='non_bazargah_status')
        if not message:
            logger.info(f"Rendered message empty for NonBazargahPurchase {instance.id} state {new_state}")
            return False

        phone_numbers = instance.customer.get_all_phone_numbers(instance, True) if instance.customer else []
        if not phone_numbers:
            logger.info(f"No phone numbers for NonBazargahPurchase {instance.id}")
            return False

        results = []
        for phone in phone_numbers:
            try:
                # Do not pass NonBazargahPurchase instance to SmsQueue.purchase FK (it's core.Purchase).
                q = sms_apis.queue_sms(phone, message, notification_type=new_state, purchase=None)
                results.append(q)
            except Exception as e:
                logger.exception(f"Error queueing SMS for NonBazargahPurchase {instance.id} to {phone}: {e}")
                continue

        if any(results):
            logger.info(f"Queued non-bazargah SMS for {instance.id} state {new_state}")
            return True
        return False
    except Exception as e:
        logger.exception(f"Error in _send_sms_for_non_bazargah_state_change for {instance.id}: {e}")
        return False


@receiver(pre_save, sender=NonBazargahPurchase, dispatch_uid="track_non_bazargah_state_change")
def track_non_bazargah_state_change(sender, instance, **kwargs):
    """Record old state on the instance to detect direct state changes (similar to Purchase flow)"""
    if instance.pk:
        try:
            old = NonBazargahPurchase.objects.get(pk=instance.pk)
            instance._old_state = old.state
        except NonBazargahPurchase.DoesNotExist:
            instance._old_state = None
    else:
        instance._old_state = None


@receiver(post_save, sender=NonBazargahPurchase, dispatch_uid="handle_non_bazargah_state_change")
def handle_non_bazargah_state_change(sender, instance, created, **kwargs):
    """
    When NonBazargahPurchase state changes, queue SMS using the non_bazargah_status templates
    This mirrors the logic used for regular Purchase in core.zignals
    """
    # Only act on updates
    if created:
        return

    old_state = getattr(instance, '_old_state', None)
    current_state = instance.state

    # If state didn't change, nothing to do
    if not old_state or old_state == current_state:
        return

    logger.info(f"NonBazargahPurchase state changed {old_state} -> {current_state} for {instance.id}")
    # Delegate to helper that builds context, renders template and queues SMSs (with duplicate protection)
    try:
        _send_sms_for_non_bazargah_state_change(instance, previous_state=old_state, new_state=current_state, notes="تغییر وضعیت توسط سیستم")
    except Exception as e:
        logger.exception(f"Error handling NonBazargahPurchase state change for {instance.id}: {e}")
