from django.utils import timezone
import json
from .models import SmsLog, SmsQueue, is_celery_active, SmsTemplate
from sms_ir import SmsIr
from django.conf import settings
from core.templatetags.custom_filters import to_persian_digits
import re
from django.db import connection

# Get API key and line number from settings
api_key = settings.SMS_API_KEY
linenumber = settings.SMS_LINE_NUMBER

sms_account = SmsIr(api_key, linenumber)


def render_template(template_type, context_data):
    """
    Render a template with the given context data
    
    Args:
        template_type (str): Type of template to render ('new_purchase', 'payment_confirmation', etc.)
                            OR status from Purchase.STATUS_CHOICES
        context_data (dict): Dictionary of values to replace placeholders in the template
        
    Returns:
        str: Rendered template text with placeholders replaced by values
    """
    try:
        # Try to get the default template for the given status
        template = SmsTemplate.objects.filter(status=template_type, is_active=True).first()
        
        # If no default template exists, get any template of the given status
        if not template:
            template = SmsTemplate.objects.filter(status=template_type).first()
            
        # If no template found at all, return None
        if not template:
            return None
            
        # Get the template content
        content = template.content
        
        # پردازش متغیرهای ساده
        for key, value in context_data.items():
            # Use regex to find placeholders with any amount of whitespace
            placeholder_pattern = r'{{\s*' + re.escape(key) + r'\s*}}'
            # Convert value to string and Persian digits if it's a number
            str_value = str(value) if value is not None else ''
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
                str_value = to_persian_digits(value)
            # Replace the placeholder with the value
            content = re.sub(placeholder_pattern, str_value, content)
        
        # پردازش متغیرهای ساختاری (با نقطه)
        # برای مثال customer.name یا purchase.invoice_id
        for model_name in ['customer', 'purchase', 'cargo']:
            if model_name in context_data and isinstance(context_data[model_name], object):
                model_obj = context_data[model_name]
                # جستجوی الگوهای متغیر با نقطه
                pattern = r'{{\s*' + model_name + r'\.([a-zA-Z0-9_]+)\s*}}'
                matches = re.finditer(pattern, content)
                
                for match in matches:
                    field_name = match.group(1)
                    try:
                        # تلاش برای دستیابی به فیلد مورد نظر
                        field_value = getattr(model_obj, field_name, '')
                        # تبدیل به رشته و اعداد فارسی در صورت لزوم
                        str_value = str(field_value) if field_value is not None else ''
                        if isinstance(field_value, (int, float)) or (isinstance(field_value, str) and field_value.isdigit()):
                            str_value = to_persian_digits(field_value)
                        # جایگزینی متغیر با مقدار
                        placeholder = match.group(0)  # کل عبارت {{ model.field }}
                        content = content.replace(placeholder, str_value)
                    except (AttributeError, Exception) as e:
                        print(f"Error accessing {field_name} in {model_name}: {str(e)}")
            
        return content
    except Exception as e:
        print(f"Error rendering template: {e}")
        return None


def send_purchase_status_notification(purchase):
    """
    Send SMS notification based on purchase status
    
    This is a generic function that replaces specific notification functions
    like send_new_purchase_notification, send_payment_confirmation, etc.
    
    Args:
        purchase: Purchase object with updated status
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    if not purchase.customer.sms_preference:
        print(f"SMS notifications disabled for customer {purchase.customer.name}")
        return False
    
    try:
        # Get all customer phone numbers
        phone_numbers = purchase.customer.get_all_phone_numbers()
        if not phone_numbers:
            print(f"No phone numbers found for customer {purchase.customer.name}")
            return False
        
        # Get purchase status
        status = purchase.state
        
        # Prepare context data for template
        context = {
            'customer': purchase.customer,
            'purchase': purchase,
            'cargo': purchase.cargo,
            'customer_name': purchase.customer.name,
            'purchase_number': purchase.purchase_number or '',
            'invoice_id': purchase.invoice_id or '',
            'order_weight': purchase.order_weight,
            'customer_price': purchase.customer_price,
            'amount_paid': purchase.amount_paid or (purchase.order_weight * purchase.customer_price if purchase.order_weight and purchase.customer_price else 0),
            'barnameh': purchase.barnameh or '',
            'shenase_takhsis': ', '.join(st.code for st in purchase.shenase_takhsis_set.all()) if hasattr(purchase, 'shenase_takhsis_set') else purchase.shenase_takhsis or '',
        }
        
        # Add cargo-related data if available
        if purchase.cargo:
            context.update({
                'cottage': purchase.cargo.cottage,
                'product_type': purchase.cargo.get_product_type_display(),
                'product_country': purchase.cargo.get_country_display(),
                'port': purchase.cargo.port,
                'loading_time': purchase.cargo.loading_time,
                'description': purchase.cargo.description,
            })
            
        # Add sales agent data if available
        sales_agents = purchase.customer.sales_agent.filter(user__is_superuser=False)
        if sales_agents:
            context.update({
                'sales_agent_phone': ', '.join([sa.phone_number for sa in sales_agents]),
                'sales_agent_name': ', '.join([sa.name for sa in sales_agents]),
            })
            
        # Add extelaf data if relevant
        if status == 'DIFFERENCE_APPROVED' and purchase.extelaf_type and purchase.extelaf_weight:
            context.update({
                'extelaf_type': purchase.extelaf_type,
                'extelaf_weight': purchase.extelaf_weight,
                'extelaf_amount': purchase.extelaf_amount,
            })
        
        # Render the template based on purchase status
        message = render_template(status, context)
        
        # If no template found, log and return
        if not message:
            print(f"No template found for status {status} ({purchase.get_state_display()})")
            return False
            
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            try:
                result = queue_sms(phone, message, notification_type=status, purchase=purchase)
                results.append(result)
                print(f"SMS queued for {phone} for purchase {purchase.invoice_id}, status: {status}")
            except Exception as e:
                print(f"Error queueing SMS for {phone}: {e}")
                # Continue to the next phone number if one fails
                continue
        
        sms_sent = any(results)
        
        # If SMS was sent and the purchase status is INITIATED, change status to SMS_SENT
        if sms_sent and status == 'INITIATED' and purchase.send_cottage_sms:
            # We need to update via raw SQL or get_or_create to avoid infinite recursion
            # because change_state would call this function again
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_purchase SET state = %s WHERE id = %s",
                    ['SMS_SENT', purchase.id]
                )
            # Also update the state field of the purchase instance
            purchase.state = 'SMS_SENT'
            
        print(f"SMS notification result for purchase {purchase.invoice_id}, status {status}: {'Success' if sms_sent else 'Failed'}")
        # Return True if at least one message was queued successfully
        return sms_sent
    except Exception as e:
        import traceback
        print(f"Error in send_purchase_status_notification for purchase {purchase.id}: {e}")
        print(traceback.format_exc())
        return False

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
    return None
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
        
        customer = purchase.customer
        if not customer:
            print(f"No customer found for purchase {purchase.id}")
            return False
        
        # Prepare context data for template
        context = {
            'customer_name': customer.name,
            'purchase_number': purchase.purchase_number or '',
            'invoice_id': purchase.invoice_id or '',
            'order_weight': purchase.order_weight,
            'customer_price': purchase.customer_price,
            'amount_paid': purchase.order_weight * purchase.customer_price if purchase.order_weight and purchase.customer_price else 0,
            'cottage': cargo.cottage,
            'product_type': cargo.get_product_type_display(),
            'product_country': cargo.get_country_display(),
            'sales_agent_phone': ', '.join([sa.phone_number for sa in customer.sales_agent.filter(user__is_superuser=False)]),
            'sales_agent_name': ', '.join([sa.name for sa in customer.sales_agent.filter(user__is_superuser=False)]),
            'payment_method': purchase.payment_method,
            'port': cargo.port,
            'loading_time': cargo.loading_time,
            'description': cargo.description,
            'weight': purchase.order_weight,
            'cargo_type': cargo.get_product_type_display(),
            'cargo_country': cargo.get_country_display(),
        }
        
        # Render the template
        message = render_template('new_purchase', context)
        
        # If no template found, use the hardcoded message as fallback
        if not message:
            message = (
                f"با سلام؛\n\n"
                f"{context['product_type']} {context['product_country']}\n"
                f"کوتاژ: {to_persian_digits(cargo.cottage)}\n"
                f"فی: {to_persian_digits(purchase.customer_price)} ریال\n"
                f"به نام شرکت تأمین نهاده سیمرغ\n\n"
                f"طی مذاکره تلفنی درخواست خرید شما به وزن {to_persian_digits(purchase.order_weight)} کیلوگرم و معادل {to_persian_digits(purchase.order_weight * purchase.customer_price)} ریال میباشد، لطفا درخواست خرید به صورت نقدی از طریق سامانه بازارگاه ثبت گردد.\n\n"
                f"پشتیبان تلفنی شما:\n"
                f"{context['sales_agent_phone']}\n"
                f"{context['sales_agent_name']}"
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
        
        # Prepare context data for template
        context = {
            'customer_name': purchase.customer.name,
            'purchase_number': purchase.purchase_number or '',
            'invoice_id': purchase.invoice_id or '',
            'amount_paid': purchase.amount_paid,
            'shenase_takhsis': ', '.join(to_persian_digits(st.code) for st in purchase.shenase_takhsis_set.all()),
        }
        
        # Render the template
        message = render_template('payment_confirmation', context)
        
        # If no template found, use the hardcoded message as fallback
        if not message:
            message = (
                f"{purchase.customer.name} گرامی،\n"
                f"پرداخت شما برای سفارش {to_persian_digits(purchase.purchase_number)} به مبلغ {to_persian_digits(purchase.amount_paid)} ریال تأیید شد.\n"
                f"شناسه/شناسه‌های تخصیص: {context['shenase_takhsis']}\n"
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
        
        # Prepare context data for template
        context = {
            'customer_name': purchase.customer.name,
            'purchase_number': purchase.purchase_number or '',
            'invoice_id': purchase.invoice_id or '',
        }
        
        # Render the template
        message = render_template('address_notification', context)
        
        # If no template found, use the hardcoded message as fallback
        if not message:
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
        
        # Prepare context data for template
        context = {
            'customer_name': purchase.customer.name,
            'purchase_number': purchase.purchase_number or '',
            'invoice_id': purchase.invoice_id or '',
            'barnameh': purchase.barnameh or '',
        }
        
        # Render the template
        message = render_template('barnameh_notification', context)
        
        # If no template found, use the hardcoded message as fallback
        if not message:
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

def check_missing_templates():
    """
    Check if there are any purchase status types without corresponding SMS templates
    Returns a list of status types that don't have templates
    """
    from .models import SmsTemplate
    from core.PurchaseModel import Purchase
    
    # Get all possible purchase status choices
    all_statuses = [status[0] for status in Purchase.STATUS_CHOICES]
    
    # Get all statuses that have templates
    template_statuses = SmsTemplate.objects.values_list('status', flat=True).distinct()
    
    # Find statuses without templates
    missing_templates = []
    for status in all_statuses:
        if status not in template_statuses:
            status_display = dict(Purchase.STATUS_CHOICES).get(status, status)
            missing_templates.append((status, status_display))
    
    return missing_templates

def create_default_templates(replace_existing=False):
    """
    Create default templates for all purchase statuses if they don't exist
    
    Args:
        replace_existing (bool): If True, will replace existing templates
                               If False, will only create templates for statuses without templates
                               
    Returns:
        tuple: (created_count, updated_count, skipped_count)
    """
    from .models import SmsTemplate
    from core.PurchaseModel import Purchase
    
    # Default template messages for each status
    default_templates = {
        'INITIATED': 'مشتری گرامی {{customer_name}}، \nخرید جدید شما با شماره {{purchase_number}} با موفقیت ثبت شد. \nنوع کالا: {{product_type}} {{product_country}}\nوزن: {{order_weight}} کیلوگرم\nقیمت: {{customer_price}} ریال',
        'SMS_SENT': 'مشتری گرامی {{customer_name}}، \nکالای {{product_type}} {{product_country}} به وزن {{order_weight}} کیلوگرم و قیمت {{customer_price}} ریال برای شما ثبت شد. کوتاژ: {{cottage}}',
        'BAZAARGAH_CONFIRMED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} در بازارگاه تایید شد. نوع کالا: {{product_type}} {{product_country}}',
        'ALLOCATION_REGISTERED': 'مشتری گرامی {{customer_name}}، \nشناسه تخصیص برای خرید شما با شماره {{purchase_number}} ثبت گردید. منتظر تایید لجستیک باشید.',
        'ALLOCATION_APPROVED': 'مشتری گرامی {{customer_name}}، \nشناسه تخصیص برای خرید شما با شماره {{purchase_number}} تایید شد.',
        'PAYMENT_VERIFIED': 'مشتری گرامی {{customer_name}}، \nپرداخت شما برای خرید {{purchase_number}} به مبلغ {{amount_paid}} ریال تایید شد.\nشناسه‌های تخصیص: {{shenase_takhsis}}',
        'VENDOR_SETTLED': 'مشتری گرامی {{customer_name}}، \nتسویه با واردکننده برای خرید شما با شماره {{purchase_number}} انجام شد.',
        'ADDRESS_SENT': 'مشتری گرامی {{customer_name}}، \nآدرس ارسال برای خرید شما با شماره {{purchase_number}} به واردکننده ارسال شد. به زودی اطلاعات ارسال برای شما پیامک می‌شود.',
        'SENT_TO_SHIPPING': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} به باربری ارسال شد.',
        'BARNAMEH_ISSUED': 'مشتری گرامی {{customer_name}}، \nبارنامه برای خرید شما با شماره {{purchase_number}} صادر شد. شماره بارنامه: {{barnameh}}',
        'DELIVERED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} به وزن {{order_weight}} کیلوگرم تحویل داده شد. از انتخاب شما متشکریم.',
        'DIFFERENCE_APPROVED': 'مشتری گرامی {{customer_name}}، \nاختلاف {{extelaf_type}} برای خرید شما با شماره {{purchase_number}} به میزان {{extelaf_weight}} کیلوگرم و مبلغ {{extelaf_amount}} ریال تایید شد.',
        'DIFFERENCE_DEPOSITED': 'مشتری گرامی {{customer_name}}، \nمبلغ اختلاف برای خرید شما با شماره {{purchase_number}} واریز شد.',
        'RECEIPT_SUBMITTED': 'مشتری گرامی {{customer_name}}، \nرسید واریز برای خرید شما با شماره {{purchase_number}} ثبت شد.',
        'INVOICE_ISSUED': 'مشتری گرامی {{customer_name}}، \nفاکتور خرید شما با شماره {{purchase_number}} صادر شد.',
        'COMPLETED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} با موفقیت به اتمام رسید. از انتخاب شما متشکریم.'
    }
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    # Create templates for each status
    for status, message in default_templates.items():
        # Check if template already exists
        existing_template = SmsTemplate.objects.filter(status=status, is_active=True).first()
        
        if existing_template and not replace_existing:
            skipped_count += 1
            continue
            
        if existing_template and replace_existing:
            existing_template.content = message
            existing_template.save()
            updated_count += 1
            continue
            
        # Get display name for the status
        status_display = dict(Purchase.STATUS_CHOICES).get(status, status)
        
        # Create new template
        SmsTemplate.objects.create(
            name=f"قالب پیش‌فرض {status_display}",
            status=status,
            content=message,
            description=f"قالب پیش‌فرض برای وضعیت {status_display}",
            is_active=True
        )
        created_count += 1
    
    return (created_count, updated_count, skipped_count)

