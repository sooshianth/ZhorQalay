from django.utils import timezone
import json
from .models import SmsLog, SmsQueue, is_celery_active
from sms_ir import SmsIr
from django.conf import settings
from core.templatetags.custom_filters import to_persian_digits

# Get API key and line number from settings
api_key = settings.SMS_API_KEY
linenumber = settings.SMS_LINE_NUMBER

sms_account = SmsIr(api_key, linenumber)



def send_instant_sms(number:str, message:str, sms_account=sms_account):
    """
    Legacy function for immediate SMS sending. Now adds to queue with immediate processing flag.
    """
    if True: # is_celery_active:
        try:
            queue_sms(number, message, notification_type='custom')
            return True
        except Exception as e:
            print(f"SMS queueing error: {e}")
            return None
    else:
        try:
            response = sms_account.send_sms(number, message)
            if response:
                # Log the sent message
                SmsLog.objects.create(
                    recipient_number=number,
                    message=message,
                    notification_type='custom',
                    status='sent',
                    api_response=json.dumps(response) if response else None
                )
            return response
        except Exception as e:
            print(f"SMS sending error: {e}")
            return None

def queue_sms(number:str, message:str, notification_type='custom', purchase=None, suspended=False, scheduled_for=None):
    # return None
    """
    Add SMS to the queue for batch processing
    """
    try:
        if not number or not message:
            raise ValueError("شماره تلفن و متن پیام نمی‌توانند خالی باشند")
            
        # Clean up the phone number format
        if number.startswith('+98'):
            number = '0' + number[3:]
        elif not number.startswith('0'):
            number = '0' + number
            
        # Ensure the number is valid (11 digits starting with 09)
        if not (number.startswith('09') and len(number) == 11):
            # Try adding 0 before 9 if number starts with 9
            if number.startswith('9') and len(number) == 10:
                number = '0' + number
            else:
                raise ValueError(f"فرمت شماره تلفن {number} نامعتبر است. باید با 09 شروع شود و 11 رقم باشد.")
                
        # Create queue entry
        status = 'suspended' if suspended else 'pending'
        
        sms_queue_data = {
            'recipient_number': number,
            'message': message,
            'notification_type': notification_type,
            'status': status,
            'is_suspended': suspended,
            'purchase': purchase
        }
        
        if scheduled_for:
            sms_queue_data['scheduled_for'] = scheduled_for
            
        sms_queue = SmsQueue.objects.create(**sms_queue_data)
        return sms_queue
    except Exception as e:
        print(f"SMS queueing error: {e}")
        raise  # Re-raise the exception to be handled by the caller

def process_sms_queue(batch_size=20, sms_account=sms_account):
    """
    Process a batch of queued SMS messages
    To be run by a scheduled task (e.g., celery, cron job)
    """
    # Get pending, non-suspended messages ordered by scheduled time
    pending_messages = SmsQueue.objects.filter(
        status='pending',
        is_suspended=False,
    ).order_by('scheduled_for', 'created_at')[:batch_size]
    
    if not pending_messages:
        print("No pending messages found to process")
        return []

    results = []
    for sms in pending_messages:
        try:
            # ارسال پیام بدون پارامتر linenumber
            api_key = settings.SMS_API_KEY
            linenumber = settings.SMS_LINE_NUMBER
            sms_account = SmsIr(api_key, linenumber)

            result = sms_account.send_sms(sms.recipient_number, sms.message)
            
            print(f"SMS send result for {sms.recipient_number}: {result}")
            
            # بررسی نتیجه ارسال پیام
            if True: # result and '200' in result:
                # پیام با موفقیت ارسال شده است
                sms.status = 'sent'
                sms.sent_at = timezone.now()
                sms.save()
                
                # ثبت در لاگ
                SmsLog.objects.create(
                    recipient_number=sms.recipient_number,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='sent',
                    api_response=json.dumps(result),
                    purchase=sms.purchase
                )
                
                results.append({"id": sms.id, "status": "sent", "result": result})
            else:
                # پیام با موفقیت ارسال نشده است
                sms.status = 'failed'
                sms.retry_count += 1
                sms.save()
                
                # ثبت در لاگ خطا
                SmsLog.objects.create(
                    recipient_number=sms.recipient_number,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='failed',
                    api_response=json.dumps(result) if result else None,
                    purchase=sms.purchase
                )
                
                results.append({"id": sms.id, "status": "failed", "error": f"Unexpected response: {result}"})
        except Exception as e:
            # sms.status = 'failed'
            # sms.retry_count += 1
            # sms.save()
            
            # # ثبت در لاگ خطا
            # SmsLog.objects.create(
            #     recipient_number=sms.recipient_number,
            #     message=sms.message,
            #     notification_type=sms.notification_type,
            #     status='failed',
            #     api_response=json.dumps({"error": str(e)}),
            #     purchase=sms.purchase
            # )
            
            # results.append({"id": sms.id, "status": "failed", "error": str(e)})
            print(f"Error processing SMS {sms.id}: {e}")
    
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
    
    try:
        # Get all customer phone numbers instead of just the primary one
        phone_numbers = purchase.customer.get_all_phone_numbers()
        if not phone_numbers:
            print(f"No phone numbers found for customer {purchase.customer.name}")
            return False
        
        cargo = purchase.cargo
        if not cargo:
            print(f"No cargo found for purchase {purchase.id}")
            return False
            
        product_name = cargo.get_product_type_display()
        country = cargo.get_country_display()
        
        message = (
            f"با سلام؛\n\n"
            f"{product_name} {country}\n"
            f"کوتاژ: {to_persian_digits(cargo.cottage)}\n"
            f"فی: {to_persian_digits(purchase.customer_price)} ریال\n"
            f"به نام شرکت تأمین نهاده سیمرغ\n\n"
            f"طی مذاکره تلفنی درخواست خرید شما به وزن {to_persian_digits(purchase.order_weight)} کیلوگرم و معادل {to_persian_digits(purchase.order_weight * purchase.customer_price)} ریال میباشد، لطفا درخواست خرید به صورت نقدی از طریق سامانه بازارگاه ثبت گردد.\n\n"
            f"پشتیبان تلفنی شما:\n"
            f"{', '.join([to_persian_digits(sa.phone_number) for sa in purchase.customer.sales_agent.filter(user__is_superuser=False)])}\n"
            f"{', '.join([sa.name for sa in purchase.customer.sales_agent.filter(user__is_superuser=False)])}"
        )
        
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            result = queue_sms(phone, message, notification_type='new_purchase', purchase=purchase)
            results.append(result)
            
        # Return True if at least one message was queued successfully
        return any(results)
    except Exception as e:
        print(f"Error in send_new_purchase_notification: {e}")
        return False

def send_payment_confirmation(purchase):
    """
    Queue SMS notification when purchase is financially approved
    """
    if not purchase.customer.sms_preference:
        return False
    
    try:
        # Get all customer phone numbers instead of just the primary one
        phone_numbers = purchase.customer.get_all_phone_numbers()
        if not phone_numbers:
            print(f"No phone numbers found for customer {purchase.customer.name}")
            return False
        
        message = (
            f"{purchase.customer.name} گرامی،\n"
            f"پرداخت شما برای سفارش {to_persian_digits(purchase.purchase_number)} به مبلغ {to_persian_digits(purchase.amount_paid)} ریال تأیید شد.\n"
            f"شناسه/شناسه‌های تخصیص: {', '.join(to_persian_digits(st.code) for st in purchase.shenase_takhsis_set.all())}\n"
            f"به زودی اطلاعات ارسال برای شما پیامک می‌شود.\n"
            f"شرکت تأمین نهاده سیمرغ"
        )
        
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            result = queue_sms(phone, message, notification_type='payment_confirmation', purchase=purchase)
            results.append(result)
            
        # Return True if at least one message was queued successfully
        return any(results)
    except Exception as e:
        print(f"Error in send_payment_confirmation: {e}")
        return False

def send_address_notification(purchase):
    """
    Queue SMS notification when address is sent to importer
    """
    if not purchase.customer.sms_preference:
        return False
    
    try:
        # Get all customer phone numbers instead of just the primary one
        phone_numbers = purchase.customer.get_all_phone_numbers()
        if not phone_numbers:
            print(f"No phone numbers found for customer {purchase.customer.name}")
            return False
        
        message = (
            f"مشتری گرامی {purchase.customer.name}،\n"
            f"آدرس ارسال برای سفارش {to_persian_digits(purchase.purchase_number)} به واردکننده ارسال شد.\n"
            f"به زودی شماره بارنامه برای شما پیامک می‌شود.\n"
            f"شرکت تأمین نهاده سیمرغ"
        )
        
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            result = queue_sms(phone, message, notification_type='address_notification', purchase=purchase)
            results.append(result)
            
        # Return True if at least one message was queued successfully
        return any(results)
    except Exception as e:
        print(f"Error in send_address_notification: {e}")
        return False

def send_barnameh_notification(purchase):
    """
    Queue SMS notification when shipping info (barnameh) is issued
    """
    if not purchase.customer.sms_preference:
        return False
    
    try:
        # Get all customer phone numbers instead of just the primary one
        phone_numbers = purchase.customer.get_all_phone_numbers()
        if not phone_numbers:
            print(f"No phone numbers found for customer {purchase.customer.name}")
            return False
        
        message = (
            f"مشتری گرامی {purchase.customer.name}،\n"
            f"بارنامه برای سفارش {to_persian_digits(purchase.purchase_number)} صادر شد.\n"
            f" شماره بارنامه: {to_persian_digits(purchase.barnameh)}\n"
            f"به زودی محموله شما ارسال خواهد شد.\n"
            f"شرکت تأمین نهاده سیمرغ"
        )
        
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            result = queue_sms(phone, message, notification_type='barnameh_notification', purchase=purchase)
            results.append(result)
            
        # Return True if at least one message was queued successfully
        return any(results)
    except Exception as e:
        print(f"Error in send_barnameh_notification: {e}")
        return False

def send_extelaf_notification(purchase):
    """
    Queue SMS notification when there's a weight difference (extelaf) of type "sarak"
    """
    if not purchase.customer.sms_preference or purchase.extelaf_type != 'سرک':
        return False
    
    try:
        # Get all customer phone numbers instead of just the primary one
        phone_numbers = purchase.customer.get_all_phone_numbers()
        if not phone_numbers:
            print(f"No phone numbers found for customer {purchase.customer.name}")
            return False
        
        message = (
            f"مشتری گرامی {purchase.customer.name}،\n"
            f"سفارش {to_persian_digits(purchase.purchase_number)} با اختلاف وزن (سرک) به میزان {to_persian_digits(purchase.extelaf_weight)} کیلوگرم "
            f"تحویل شده است.\n"
            f"مبلغ قابل پرداخت: {to_persian_digits(purchase.extelaf_amount)} ریال\n"
            f"لطفا نسبت به پرداخت مبلغ اقدام فرمایید.\n"
            f"شرکت تأمین نهاده سیمرغ"
        )
        
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            result = queue_sms(phone, message, notification_type='extelaf_notification', purchase=purchase)
            results.append(result)
            
        # Return True if at least one message was queued successfully
        return any(results)
    except Exception as e:
        print(f"Error in send_extelaf_notification: {e}")
        return False

