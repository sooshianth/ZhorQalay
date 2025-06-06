from django.utils import timezone
from .models import WhatsappQueue, WhatsappLog, WhatsappTemplate
from .utils import send_whatsapp_message
import logging
import re

logger = logging.getLogger(__name__)

def queue_whatsapp_message(recipient_number, message, notification_type='custom', scheduled_for=None, purchase=None, template_type=None):
    """
    اضافه کردن پیام واتساپ به صف ارسال
    """
    try:
        if scheduled_for is None:
            scheduled_for = timezone.now()
        
        whatsapp_queue = WhatsappQueue.objects.create(
            recipient_number=recipient_number,
            message=message,
            template_type=template_type or notification_type,
            notification_type=notification_type,
            status='pending',
            scheduled_for=scheduled_for,
            purchase=purchase
        )
        
        logger.info(f"پیام واتساپ به شماره {recipient_number} به صف ارسال اضافه شد.")
        return whatsapp_queue
        
    except Exception as e:
        logger.error(f"خطا در اضافه کردن پیام واتساپ به صف: {str(e)}")
        raise

def process_whatsapp_queue():
    """
    پردازش صف پیام‌های واتساپ
    """
    results = []
    
    # پیام‌های آماده ارسال را بگیر
    pending_messages = WhatsappQueue.objects.filter(
        status='pending',
        is_suspended=False,
        scheduled_for__lte=timezone.now()
    ).order_by('scheduled_for')[:10]  # حداکثر 10 پیام در هر بار
    
    for queue_item in pending_messages:
        try:
            # اگر پیام مرتبط با خرید است و مشتری دارد، به همه شماره‌های مشتری ارسال شود
            if queue_item.purchase and hasattr(queue_item.purchase, 'customer') and queue_item.purchase.customer:
                customer = queue_item.purchase.customer
                phone_numbers = [customer.get_primary_phone()]
                phone_numbers = [phone for phone in phone_numbers if phone]  # حذف شماره‌های خالی
                
                if not phone_numbers:
                    queue_item.status = 'failed'
                    queue_item.save()
                    results.append({
                        'queue_item_id': queue_item.id,
                        'status': 'failed',
                        'message': f'هیچ شماره تلفنی برای مشتری {customer.name} یافت نشد.'
                    })
                    continue
                
                success_count = 0
                for phone in phone_numbers:
                    # پردازش قالب با داده‌های خرید
                    processed_message = process_template_placeholders(queue_item.message, queue_item.purchase, customer)
                    
                    success = send_whatsapp_message(phone, queue_item.template_type, {
                        'customer_name': customer.name,
                        'purchase_number': queue_item.purchase.purchase_number,
                        'message': processed_message
                    })
                    
                    if success:
                        # ثبت در لاگ
                        WhatsappLog.objects.create(
                            recipient_number=phone,
                            message=processed_message,
                            template_type=queue_item.template_type,
                            status='sent',
                            purchase=queue_item.purchase
                        )
                        success_count += 1
                
                if success_count > 0:
                    queue_item.status = 'sent'
                    queue_item.sent_at = timezone.now()
                    queue_item.save()
                    
                    results.append({
                        'queue_item_id': queue_item.id,
                        'status': 'sent',
                        'message': f'پیام واتساپ به {success_count} شماره ارسال شد.'
                    })
                else:
                    queue_item.status = 'failed'
                    queue_item.retry_count += 1
                    queue_item.save()
                    
                    results.append({
                        'queue_item_id': queue_item.id,
                        'status': 'failed',
                        'message': 'ارسال پیام واتساپ ناموفق بود.'
                    })
            else:
                # ارسال به یک شماره تکی
                success = send_whatsapp_message(queue_item.recipient_number, queue_item.template_type, {})
                
                if success:
                    queue_item.status = 'sent'
                    queue_item.sent_at = timezone.now()
                    queue_item.save()
                    
                    # ثبت در لاگ
                    WhatsappLog.objects.create(
                        recipient_number=queue_item.recipient_number,
                        message=queue_item.message,
                        template_type=queue_item.template_type,
                        status='sent',
                        purchase=queue_item.purchase
                    )
                    
                    results.append({
                        'queue_item_id': queue_item.id,
                        'status': 'sent',
                        'message': 'پیام واتساپ با موفقیت ارسال شد.'
                    })
                else:
                    queue_item.status = 'failed'
                    queue_item.retry_count += 1
                    queue_item.save()
                    
                    results.append({
                        'queue_item_id': queue_item.id,
                        'status': 'failed',
                        'message': 'ارسال پیام واتساپ ناموفق بود.'
                    })
                    
        except Exception as e:
            logger.error(f"خطا در پردازش پیام واتساپ {queue_item.id}: {str(e)}")
            queue_item.status = 'failed'
            queue_item.retry_count += 1
            queue_item.save()
            
            results.append({
                'queue_item_id': queue_item.id,
                'status': 'failed',
                'message': f'خطا: {str(e)}'
            })
    
    return results

def process_template_placeholders(message, purchase=None, customer=None):
    """
    پردازش جایگزین‌های قالب در پیام
    """
    if not purchase and not customer:
        return message
    
    processed_message = message
    
    # داده‌های مشتری
    if customer:
        processed_message = processed_message.replace('{{customer_name}}', customer.name or '')
    
    # داده‌های خرید
    if purchase:
        replacements = {
            '{{purchase_number}}': str(purchase.purchase_number or ''),
            '{{invoice_id}}': str(purchase.invoice_id or ''),
            '{{order_weight}}': str(purchase.order_weight or ''),
            '{{customer_price}}': str(purchase.customer_price or ''),
            '{{amount_paid}}': str(purchase.amount_paid or ''),
            '{{barnameh}}': str(purchase.barnameh or ''),
            '{{barnameh_date}}': str(purchase.barnameh_date or ''),
            '{{driver_name}}': str(purchase.driver_name or ''),
            '{{driver_phone}}': str(purchase.driver_phone or ''),
            '{{shenase_takhsis}}': str(purchase.shenase_takhsis or ''),
        }
        
        # اضافه کردن داده‌های اختلاف اگر موجود باشد
        if hasattr(purchase, 'extelaf_weight'):
            replacements['{{extelaf_weight}}'] = str(purchase.extelaf_weight or '')
            replacements['{{extelaf_amount}}'] = str(purchase.extelaf_amount or '')
            replacements['{{extelaf_type}}'] = str(purchase.extelaf_type or '')
        
        # اضافه کردن داده‌های کارشناس فروش اگر موجود باشد
        if customer and hasattr(customer, 'sales_agent') and customer.sales_agent:
            replacements['{{sales_agent_name}}'] = str(customer.sales_agent.name or '')
            replacements['{{sales_agent_phone}}'] = str(customer.sales_agent.phone_number or '')
            replacements['{{dakheli_number}}'] = str(getattr(customer.sales_agent, 'dakheli_number', '3'))
        
        for placeholder, value in replacements.items():
            processed_message = processed_message.replace(placeholder, value)
    
    return processed_message

def check_missing_whatsapp_templates():
    """
    بررسی قالب‌های مفقود واتساپ
    """
    from core.PurchaseModel import Purchase
    
    existing_statuses = set(WhatsappTemplate.objects.values_list('status', flat=True))
    all_statuses = set([status[0] for status in Purchase.STATUS_CHOICES])
    
    missing_statuses = all_statuses - existing_statuses
    
    missing_templates = []
    for status in missing_statuses:
        status_display = dict(Purchase.STATUS_CHOICES).get(status, status)
        missing_templates.append({
            'status': status,
            'status_display': status_display
        })
    
    return missing_templates

def create_default_whatsapp_templates(replace_existing=False):
    """
    ایجاد قالب‌های پیش‌فرض واتساپ
    """
    default_templates = get_default_whatsapp_templates()
    
    created = 0
    updated = 0
    skipped = 0
    
    for status, content in default_templates.items():
        # بررسی وجود قالب
        existing_template = WhatsappTemplate.objects.filter(status=status, is_active=True).first()
        
        if existing_template:
            if replace_existing:
                existing_template.content = content
                existing_template.updated_at = timezone.now()
                existing_template.save()
                updated += 1
            else:
                skipped += 1
        else:
            # ایجاد قالب جدید
            status_display = dict(WhatsappTemplate.STATUS_CHOICES).get(status, status)
            
            WhatsappTemplate.objects.create(
                name=f'قالب پیش‌فرض {status_display}',
                status=status,
                template_type='purchase',  # نوع پیش‌فرض
                content=content,
                description=f'قالب پیش‌فرض برای وضعیت {status_display}',
                is_active=True
            )
            created += 1
    
    return created, updated, skipped

def get_default_whatsapp_templates():
    """
    تولید قالب‌های پیش‌فرض برای وضعیت‌های مختلف خرید
    """
    return {
        'INITIATED': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} در بازارگاه به صورت نقدی ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.\nاز خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚\nجهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'SMS_SENT': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} در بازارگاه به صورت نقدی ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.\nاز خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚\nجهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'PAYMENT_VERIFIED': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} در بازارگاه به صورت نقدی ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.\nاز خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚\nجهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'ALLOCATION_APPROVED': 'تخصیص شما به شماره {{shenase_takhsis}} در سامانه بازارگاه ثبت گردید. ✅\nبزودی آدرس شما برای وارد کننده و سپس باربری ارسال خواهد شد.\nشرکت تامین نهاده سیمرغ',
        'ADDRESS_SENT': '{{customer_name}}؛\nخرید شما با شماره خرید {{purchase_number}} جهت بارگیری به وارد کننده ارسال گردید. ✅\nما با تمام توان پیگیر ارسال بار شما هستیم تا هرچه سریع‌تر به شما تحویل گردد؛ با این وجود جهت پیگیری بار میتوانید با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'WAITING_FOR_BARNAMEH': '{{customer_name}}؛\nخرید شما با شماره خرید {{purchase_number}} جهت بارگیری به وارد کننده ارسال گردید. ✅\nما با تمام توان پیگیر ارسال بار شما هستیم تا هرچه سریع‌تر به شما تحویل گردد؛ با این وجود جهت پیگیری بار میتوانید با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'BARNAMEH_INCOMPLETE': '{{customer_name}} عزیز؛\nبارنامه خرید {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} :\nشماره بارنامه: {{barnameh}}\nتاریخ بارنامه: نامشخص\nشماره راننده: نامشخص\nنام راننده: نامشخص\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'BARNAMEH_ISSUED': '{{customer_name}} عزیز؛\nبارنامه خرید {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} :\nشماره بارنامه: {{barnameh}}\nتاریخ بارنامه: {{barnameh_date}}\nشماره راننده: {{driver_phone}}\nنام راننده: {{driver_name}}\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'PURCHASE_CLOSED': 'مشتری گرامی\nبارنامه خرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن خرید {{order_weight}} در بازارگاه ثبت گردید.✅\nاز خرید و اعتماد شما صمیمانه سپاسگزاریم 💚\nامیدواریم در آینده نزدیک مجددا در خدمت شما باشیم 🙏\nکارشناس فروش شما: {{sales_agent_name}}\n{{sales_agent_phone}}\n۰۲۱-۶۶۵۶۲۲۱۶ داخلی {{dakheli_number}}\nشرکت تامین نهاده سیمرغ',
        'DIFFERENCE_APPROVED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} با اختلاف وزن ({{extelaf_type}}) به میزان {{extelaf_weight}} کیلوگرم تحویل شده است. مبلغ قابل پرداخت: {{extelaf_amount}} ریال',
        'FULLY_SETTLED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} به صورت کامل تسویه شد.',
        'INVOICE_ISSUED': 'مشتری گرامی {{customer_name}}، \nفاکتور خرید شما با شماره {{purchase_number}} صادر شد.',
        'CANCELED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} لغو شده است. لطفا با کارشناس فروش تماس بگیرید.',
        'ARCHIVED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} آرشیو شده است.',
    } 