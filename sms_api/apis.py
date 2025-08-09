from django.utils import timezone
import json
from .models import SmsLog, SmsQueue, is_celery_active, SmsTemplate
from sms_ir import SmsIr
from django.conf import settings
from core.templatetags.custom_filters import to_persian_digits
import re
from django.db import connection
import logging

# Get API key and line number from settings
api_key = settings.SMS_API_KEY
linenumber = settings.SMS_LINE_NUMBER

sms_account = SmsIr(api_key, linenumber)

logger = logging.getLogger("sms_api_api")

def normalize_phone_number(phone_number):
    """
    نرمال‌سازی شماره تلفن به فرمت استاندارد (10 رقمی شروع با 9)
    
    Args:
        phone_number (str): شماره تلفن خام
        
    Returns:
        str: شماره تلفن نرمال شده یا None اگر نامعتبر باشد
    """
    if not phone_number:
        return None
    
    # تبدیل به رشته و حذف فضاهای خالی
    phone_str = str(phone_number).strip()
    
    # تبدیل اعداد فارسی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    phone_str = phone_str.translate(translation_table)
    
    # حذف کاراکترهای غیرعددی (به جز + در ابتدا)
    if phone_str.startswith('+'):
        cleaned = '+' + ''.join(c for c in phone_str[1:] if c.isdigit())
    else:
        cleaned = ''.join(c for c in phone_str if c.isdigit())
    
    # اگر هیچ عددی نداشت، None برگردان
    if not any(c.isdigit() for c in cleaned):
        return None
    
    # حذف پیشوندهای مختلف
    if cleaned.startswith('+98'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('0098'):
        cleaned = cleaned[4:]
    elif cleaned.startswith('98') and len(cleaned) >= 12:  # 98 + حداقل 10 digits
        cleaned = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) >= 11:  # 0 + حداقل 10 digits
        cleaned = cleaned[1:]
    
    # اعتبارسنجی نهایی: باید 10 رقم و شروع با 9 باشد
    if len(cleaned) == 10 and cleaned.startswith('9') and cleaned.isdigit():
        return cleaned
    
    # تلاش برای استخراج شماره معتبر از رشته طولانی‌تر
    if len(cleaned) > 10:
        for i in range(len(cleaned) - 9):
            potential_number = cleaned[i:i+10]
            if potential_number.startswith('9') and potential_number.isdigit():
                return potential_number
    
    return None

def normalize_phone_numbers_list(phone_numbers):
    """
    نرمال‌سازی لیستی از شماره‌های تلفن و حذف تکرارها
    
    Args:
        phone_numbers (list): لیست شماره‌های تلفن خام
        
    Returns:
        list: لیست شماره‌های تلفن نرمال شده و بدون تکرار
    """
    if not phone_numbers:
        return []
    
    normalized_set = set()
    for phone in phone_numbers:
        normalized = normalize_phone_number(phone)
        if normalized:
            normalized_set.add(normalized)
    
    return sorted(list(normalized_set))

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
            
            # پردازش متغیرهای با مقدار پیش‌فرض
            # الگوی {{key|default:"value"}}
            default_pattern = r'{{\s*' + re.escape(key) + r'\s*\|\s*default:\s*"([^"]*)"\s*}}'
            for match in re.finditer(default_pattern, content):
                default_value = match.group(1)
                placeholder = match.group(0)  # {{key|default:"value"}}
                if not str_value:  # اگر مقدار اصلی خالی باشد، از مقدار پیش‌فرض استفاده می‌کنیم
                    content = content.replace(placeholder, default_value)
                else:
                    content = content.replace(placeholder, str_value)
        
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
    # List of states that should receive SMS notifications
    NOTIFY_STATES = [
        'INITIATED',
        'PAYMENT_VERIFIED',    # ثبت خرید در بازارگاه
        'ALLOCATION_APPROVED', # تایید تخصیص
        'ADDRESS_SENT',        # ارسال آدرس به واردکننده
        'BARNAMEH_ISSUED',     # صدور بارنامه
        'BARNAMEH_INCOMPLETE', # بارنامه ناقص
        'PURCHASE_CLOSED',     # بستن خرید در بازارگاه
        'INVOICE_ISSUED',      # صدور فاکتور
    ]
    
    # Check if the current state should receive notifications
    if purchase.state not in NOTIFY_STATES:
        logger.info(f"Skipping SMS notification for state {purchase.state} - not in notification list")
        return False
    
    if not purchase.customer or not purchase.customer.sms_preference:
        logger.warning(f"SMS notifications disabled for customer {purchase.customer.name if purchase.customer else 'unknown'}")
        return False
    
    # پراپرتی status را از purchase.state پر میکنیم
    status = purchase.state
    
    # بررسی اینکه آیا قبلا برای این وضعیت پیامک ارسال شده است یا خیر
    from core.PurchaseModel import PurchaseStateChange
    already_sent = PurchaseStateChange.objects.filter(
        purchase=purchase, 
        new_state=status,
        sms_sent=True
    ).exists()
    
    if already_sent:
        logger.info(f"SMS already sent for purchase {purchase.id}, state {status}")
        return False
    
    try:
        # Get all customer phone numbers
        phone_numbers = purchase.customer.get_all_phone_numbers(purchase, True)
        if not phone_numbers:
            logger.warning(f"No phone numbers found for customer {purchase.customer.name}")
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
        }
        
        # Add barnameh info if available
        if hasattr(purchase, 'barnameh') and purchase.barnameh:
            context['barnameh'] = purchase.barnameh
        else:
            context['barnameh'] = ''

        # اضافه کردن اطلاعات راننده و بارنامه
        context['barnameh_date'] = getattr(purchase, 'barnameh_date', '')
        context['driver_name'] = getattr(purchase, 'driver_name', '')
        context['driver_phone'] = getattr(purchase, 'driver_phone', '')
        
        # Add takhsis info (using a safe method)
        if hasattr(purchase, 'shenase_takhsis_set') and purchase.shenase_takhsis_set.exists():
            context['shenase_takhsis'] = ', '.join(st.code for st in purchase.shenase_takhsis_set.all())
        else:
            context['shenase_takhsis'] = getattr(purchase, 'shenase_takhsis', '')
        
        # Add cargo-related data if available
        if purchase.cargo:
            cargo = purchase.cargo
            
            # Safely get cottage field (different models might have different field names)
            cottage_value = ''
            for field_name in ['cottage', 'cottage_number', 'cottage_id']:
                if hasattr(cargo, field_name):
                    cottage_value = getattr(cargo, field_name, '')
                    if cottage_value:
                        break
            context['cottage'] = cottage_value
            
            # Safely get product_type
            product_type = ''
            if hasattr(cargo, 'get_product_type_display'):
                product_type = cargo.get_product_type_display()
            else:
                product_type = getattr(cargo, 'product_type', '')
            context['product_type'] = product_type
            
            # Safely get country
            product_country = ''
            if hasattr(cargo, 'get_country_display'):
                product_country = cargo.get_country_display()
            else:
                product_country = getattr(cargo, 'country', '')
            context['product_country'] = product_country
            
            # Other cargo fields
            context['port'] = getattr(cargo, 'port', '')
            context['loading_time'] = getattr(cargo, 'loading_time', '')
            context['description'] = getattr(cargo, 'description', '')
        else:
            # Default values when no cargo is available
            context['cottage'] = ''
            context['product_type'] = ''
            context['product_country'] = ''
            context['port'] = ''
            context['loading_time'] = ''
            context['description'] = ''
            
        # Add sales agent data if available
        sales_agents = purchase.customer.sales_agent.filter(user__is_superuser=False)
        if sales_agents:
            agent_names = [agent.name for agent in sales_agents if hasattr(agent, 'name') and agent.name]
            agent_phones = [agent.phone_number for agent in sales_agents if hasattr(agent, 'phone_number') and agent.phone_number]
            
            context['sales_agent_phone'] = ', '.join(agent_phones) if agent_phones else ''
            context['sales_agent_name'] = ', '.join(agent_names) if agent_names else ''
            
            # دریافت شماره داخلی کارشناس فروش
            first_agent = sales_agents.first()
            if first_agent and hasattr(first_agent, 'dakheli_number') and first_agent.dakheli_number:
                context['dakheli_number'] = first_agent.dakheli_number
            else:
                context['dakheli_number'] = '۳'
        else:
            context['sales_agent_phone'] = ''
            context['sales_agent_name'] = ''
            context['dakheli_number'] = '۳'
            
        # Add extelaf data if relevant
        if status == 'DIFFERENCE_APPROVED' and purchase.extelaf_type and purchase.extelaf_weight:
            context.update({
                'extelaf_type': purchase.extelaf_type,
                'extelaf_weight': purchase.extelaf_weight,
                'extelaf_amount': purchase.extelaf_amount,
            })
        else:
            context['extelaf_type'] = getattr(purchase, 'extelaf_type', '')
            context['extelaf_weight'] = getattr(purchase, 'extelaf_weight', 0)
            context['extelaf_amount'] = getattr(purchase, 'extelaf_amount', 0)
        
        # Render the template based on purchase status
        message = render_template(status, context)
        
        # If no template found, log and return
        if not message:
            logger.warning(f"No template found for status {status} ({purchase.get_state_display() if hasattr(purchase, 'get_state_display') else status})")
            return False
            
        # Send to all phone numbers
        results = []
        for phone in phone_numbers:
            try:
                logger.debug(f"Queuing SMS for {phone} for purchase {purchase.invoice_id}, status: {status}")
                continue
                result = queue_sms(phone, message, notification_type=status, purchase=purchase)
                results.append(result)
                logger.info(f"SMS queued for {phone} for purchase {purchase.invoice_id}, status: {status}")
            except Exception as e:
                logger.error(f"Error queueing SMS for {phone}: {e}")
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
            
        logger.info(f"SMS notification result for purchase {purchase.invoice_id}, status {status}: {'Success' if sms_sent else 'Failed'}")
        # Return True if at least one message was queued successfully
        return sms_sent
    except Exception as e:
        import traceback
        logger.error(f"Error in send_purchase_status_notification for purchase {purchase.id}: {e}")
        logger.error(traceback.format_exc())
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
    """
    Add SMS to the queue for batch processing
    """
    try:
        if not number or not message:
            logger.error(f"SMS queue error: Empty number or message")
            raise ValueError("شماره تلفن و متن پیام نمی‌توانند خالی باشند")
            
        # استفاده از تابع نرمال‌سازی جدید
        original_number = number
        normalized_number = normalize_phone_number(number)
        
        if not normalized_number:
            logger.error(f"SMS queue error: Invalid phone number format: {original_number}")
            raise ValueError(f"فرمت شماره تلفن {original_number} نامعتبر است. باید 10 رقم باشد و با 9 شروع شود.")
        
        # تبدیل به فرمت 11 رقمی برای ذخیره (اضافه کردن 0)
        number = '0' + normalized_number
        
        # Log the SMS being queued
        purchase_info = f"Purchase: {purchase.id}" if purchase else "No purchase"
        logger.info(f"Queueing SMS to {number} (normalized from {original_number}) - Type: {notification_type} - {purchase_info}")
                
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
        logger.info(f"SMS queued successfully: Queue ID {sms_queue.id}")
        return sms_queue
    except Exception as e:
        logger.error(f"Error queueing SMS to {number}: {str(e)}")
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
        scheduled_for__lte=timezone.now()  # فقط پیام‌هایی که زمان ارسال آنها فرا رسیده
    ).order_by('scheduled_for', 'created_at')[:batch_size]
    
    count = pending_messages.count()
    if count == 0:
        logger.debug("No pending messages found to process")
        return []

    logger.info(f"Processing {count} SMS messages from queue")
    results = []
    
    for sms in pending_messages:
        try:
            recipient = sms.recipient_number
            logger.info(f"Sending SMS to {recipient} (Queue ID: {sms.id})")
            
            # تلاش برای ارسال پیامک
            response = None
            try:
                # استفاده از api_key و linenumber از تنظیمات
                response = sms_account.send_sms(recipient, sms.message)
                logger.debug(f"SMS API response for {recipient}: {response}")
            except Exception as api_error:
                logger.error(f"Error from SMS API for {recipient}: {str(api_error)}")
                response = {"error": str(api_error)}
            
            # بررسی پاسخ API و به‌روزرسانی وضعیت
            if response is not None:  # اگر پاسخی دریافت شد، حتی اگر خطا بود
                # پیام با موفقیت ارسال شده است (فرض می‌کنیم هر پاسخی نشان دهنده ارسال موفق است)
                # می‌توانید اینجا بررسی‌های دقیق‌تری انجام دهید
                sms.status = 'sent'
                sms.sent_at = timezone.now()
                sms.save()
                
                # ثبت در لاگ
                SmsLog.objects.create(
                    recipient_number=recipient,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='sent',
                    api_response=json.dumps(response) if response else None,
                    purchase=sms.purchase
                )
                
                logger.info(f"SMS sent successfully to {recipient} (Queue ID: {sms.id})")
                results.append({"id": sms.id, "status": "sent", "result": response})
            else:
                # پیام با موفقیت ارسال نشده است
                sms.status = 'failed'
                sms.retry_count += 1
                sms.save()
                
                # ثبت در لاگ خطا
                SmsLog.objects.create(
                    recipient_number=recipient,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='failed',
                    api_response=json.dumps({"error": "No response from API"}) if response is None else json.dumps(response),
                    purchase=sms.purchase
                )
                
                logger.error(f"Failed to send SMS to {recipient} (Queue ID: {sms.id}): No response from API")
                results.append({"id": sms.id, "status": "failed", "error": "No response from API"})
        except Exception as e:
            logger.exception(f"Unexpected error processing SMS queue item {sms.id}: {str(e)}")
            
            try:
                # به‌روزرسانی وضعیت پیامک در صورت بروز خطا
                sms.status = 'failed'
                sms.retry_count += 1
                sms.save()
                
                # ثبت در لاگ خطا
                SmsLog.objects.create(
                    recipient_number=sms.recipient_number,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='failed',
                    api_response=json.dumps({"error": str(e)}),
                    purchase=sms.purchase
                )
                
                results.append({"id": sms.id, "status": "failed", "error": str(e)})
            except Exception as inner_error:
                logger.exception(f"Error handling failure for SMS {sms.id}: {str(inner_error)}")
    
    # گزارش کلی
    sent_count = sum(1 for r in results if r.get('status') == 'sent')
    failed_count = sum(1 for r in results if r.get('status') == 'failed')
    logger.info(f"SMS queue processing complete: {sent_count} sent, {failed_count} failed")
    
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
        phone_numbers = purchase.customer.get_all_phone_numbers(purchase, True)
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
        phone_numbers = purchase.customer.get_all_phone_numbers(purchase)
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
        phone_numbers = purchase.customer.get_all_phone_numbers(purchase, True)
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
        phone_numbers = purchase.customer.get_all_phone_numbers(purchase, True)
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
        phone_numbers = purchase.customer.get_all_phone_numbers(purchase, True)
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
        'INITIATED': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} در بازارگاه به صورت نقدی ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.\nاز خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚\nجهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'SMS_SENT': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} در بازارگاه به صورت نقدی ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.\nاز خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚\nجهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'PAYMENT_VERIFIED': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} در بازارگاه به صورت نقدی ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.\nاز خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚\nجهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'ALLOCATION_APPROVED': 'تخصیص شما به شماره {{shenase_takhsis}} در سامانه بازارگاه ثبت گردید. ✅\nبزودی آدرس شما برای وارد کننده و سپس باربری ارسال خواهد شد.\nشرکت تامین نهاده سیمرغ',
        'ADDRESS_SENT': '{{customer_name}}؛\nخرید شما با شماره خرید {{purchase_number}} جهت بارگیری به وارد کننده ارسال گردید. ✅\nما با تمام توان پیگیر ارسال بار شما هستیم تا هرچه سریع‌تر به شما تحویل گردد؛ با این وجود جهت پیگیری بار میتوانید با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'WAITING_FOR_BARNAMEH': '{{customer_name}}؛\nخرید شما با شماره خرید {{purchase_number}} جهت بارگیری به وارد کننده ارسال گردید. ✅\nما با تمام توان پیگیر ارسال بار شما هستیم تا هرچه سریع‌تر به شما تحویل گردد؛ با این وجود جهت پیگیری بار میتوانید با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'BARNAMEH_INCOMPLETE': '{{customer_name}} عزیز؛\nبارنامه خرید {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} :\nشماره بارنامه: {{barnameh}}\nتاریخ بارنامه: نامشخص\nشماره راننده: نامشخص\nنام راننده: نامشخص\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'BARNAMEH_ISSUED': '{{customer_name}} عزیز؛\nبارنامه خرید {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} :\nشماره بارنامه: {{barnameh}}\nتاریخ بارنامه: {{barnameh_date|default:"نامشخص"}}\nشماره راننده: {{driver_phone|default:"نامشخص"}}\nنام راننده: {{driver_name|default:"نامشخص"}}\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'PURCHASE_CLOSED': 'مشتری گرامی\nبارنامه خرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن خرید {{order_weight}} در بازارگاه ثبت گردید.✅\nاز خرید و اعتماد شما صمیمانه سپاسگزاریم 💚\nامیدواریم در آینده نزدیک مجددا در خدمت شما باشیم 🙏\nکارشناس فروش شما: {{sales_agent_name}}\n{{sales_agent_phone}}\n۰۲۱-۶۶۵۶۲۲۱۶ داخلی {{dakheli_number|default:"۳"}}\nشرکت تامین نهاده سیمرغ',
        'DIFFERENCE_APPROVED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} با اختلاف وزن ({{extelaf_type}}) به میزان {{extelaf_weight}} کیلوگرم تحویل شده است. مبلغ قابل پرداخت: {{extelaf_amount}} ریال',
        'FULLY_SETTLED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} به صورت کامل تسویه شد.',
        'INVOICE_ISSUED': 'مشتری گرامی {{customer_name}}، \nفاکتور خرید شما با شماره {{purchase_number}} صادر شد.',
        'CANCELED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} لغو شده است. لطفا با کارشناس فروش تماس بگیرید.',
        'ARCHIVED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} آرشیو شده است.',
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

