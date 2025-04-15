from sms_ir import SmsIr
from django.utils import timezone
import json
from .models import SmsLog, SmsQueue


api_key='mbdRODVCB2JHUX5c3IpetXsiDXFIT6bo7JZo0PhiTFWkuIN4'
linenumber=90008316


sms_account = SmsIr(api_key, linenumber)

def send_instant_sms(number:str, message:str, sms_account=sms_account):
    """
    Legacy function for immediate SMS sending. Now adds to queue with immediate processing flag.
    """
    try:
        queue_sms(number, message, notification_type='custom')
        return True
    except Exception as e:
        print(f"SMS queueing error: {e}")
        return None

def queue_sms(number:str, message:str, notification_type='custom', purchase_id=None, suspended=False):
    """
    Add SMS to the queue for batch processing
    """
    try:
        # Clean up the phone number format
        if number.startswith('+98'):
            number = '0' + number[3:]
        elif not number.startswith('0'):
            number = '0' + number
            
        # Create queue entry
        status = 'suspended' if suspended else 'pending'
        sms_queue = SmsQueue.objects.create(
            recipient_number=number,
            message=message,
            notification_type=notification_type,
            status=status,
            is_suspended=suspended,
            purchase_id=purchase_id
        )
        return sms_queue
    except Exception as e:
        print(f"SMS queueing error: {e}")
        return None

def process_sms_queue(batch_size=20, sms_account=sms_account):
    """
    Process a batch of queued SMS messages
    To be run by a scheduled task (e.g., celery, cron job)
    """
    # Get pending, non-suspended messages ordered by scheduled time
    pending_messages = SmsQueue.objects.filter(
        status='pending',
        is_suspended=False,
        scheduled_for__lte=timezone.now()
    ).order_by('scheduled_for', 'created_at')[:batch_size]
    
    results = []
    for sms in pending_messages:
        try:
            # Send the SMS
            result = sms_account.send_sms(sms.recipient_number, sms.message, sms_account.linenumber)
            
            # Update the queue entry
            sms.status = 'sent'
            sms.sent_at = timezone.now()
            sms.save()
            
            # Log the sent message
            SmsLog.objects.create(
                recipient_number=sms.recipient_number,
                message=sms.message,
                notification_type=sms.notification_type,
                status='sent',
                api_response=json.dumps(result) if result else None,
                purchase_id=sms.purchase_id
            )
            
            results.append({"id": sms.id, "status": "sent", "result": result})
        except Exception as e:
            sms.status = 'failed'
            sms.retry_count += 1
            sms.save()
            results.append({"id": sms.id, "status": "failed", "error": str(e)})
    
    return results

def todays_sms_report(sms_account=sms_account):
    return sms_account.report_today(
        page_size=20,
        page_number=15,
        )

# Purchase notification functions
def send_new_purchase_notification(purchase):
    """
    Queue SMS notification when a new purchase is created
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    cargo = purchase.cargo
    product_name = cargo.get_product_type_display()
    country = cargo.get_country_display()
    
    message = (
        f"با سلام؛\n\n"
        f"{product_name} {country}\n"
        f"کوتاژ: {cargo.cottage}\n"
        f"فی: {purchase.customer_price} ریال\n"
        f"به نام شرکت تأمین نهاده سیمرغ\n\n"
        f"طی مذاکره تلفنی درخواست خرید شما به وزن {purchase.weight} کیلوگرم و معادل {purchase.weight * purchase.customer_price} ریال میباشد، لطفا درخواست خرید به صورت نقدی از طریق سامانه بازارگاه ثبت گردد.\n\n"
        f"پشتیبان تلفنی شما:\n"
        f"{', '.join([sa.phone_number for sa in purchase.customer.sales_agent.all()])}\n"
        f"{', '.join([sa.name for sa in purchase.customer.sales_agent.all()])}"
    )
    
    return queue_sms(number, message, notification_type='new_purchase', purchase_id=purchase.id)

def send_payment_confirmation(purchase):
    """
    Queue SMS notification when purchase is financially approved
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی {purchase.customer.name}،\n"
        f"پرداخت شما برای سفارش {purchase.invoice_id} تأیید شد.\n"
        f"به زودی اطلاعات ارسال برای شما پیامک می‌شود.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return queue_sms(number, message, notification_type='payment_confirmation', purchase_id=purchase.id)

def send_address_notification(purchase):
    """
    Queue SMS notification when address is sent to importer
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی {purchase.customer.name}،\n"
        f"آدرس ارسال برای سفارش {purchase.purchase_number} به واردکننده ارسال شد.\n"
        f"به زودی شماره بارنامه برای شما پیامک می‌شود.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return queue_sms(number, message, notification_type='address_notification', purchase_id=purchase.id)

def send_barnameh_notification(purchase):
    """
    Queue SMS notification when shipping info (barnameh) is issued
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی {purchase.customer.name}،\n"
        f"بارنامه برای سفارش {purchase.purchase_number} صادر شد.\n"
        f" شناسه تخصیص: {purchase.shenase_takhsis}\n"
        f"به زودی محموله شما ارسال خواهد شد.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return queue_sms(number, message, notification_type='barnameh_notification', purchase_id=purchase.id)

def send_extelaf_notification(purchase):
    """
    Queue SMS notification when there's a weight difference (extelaf) of type "sarak"
    """
    if not purchase.customer.sms_preference or purchase.extelaf_type != 'سرک':
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی {purchase.customer.name}،\n"
        f"سفارش {purchase.purchase_number} با اختلاف وزن (سرک) به میزان {purchase.extelaf_weight} کیلوگرم "
        f"تحویل شده است.\n"
        f"مبلغ قابل پرداخت: {purchase.extelaf_amount} ریال\n"
        f"لطفا نسبت به پرداخت مبلغ اقدام فرمایید.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return queue_sms(number, message, notification_type='extelaf_notification', purchase_id=purchase.id)

