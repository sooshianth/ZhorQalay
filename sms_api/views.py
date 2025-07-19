from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import SmsQueue, SmsLog, SmsTemplate
import datetime
import xlsxwriter
import io
from django.template.loader import get_template
from xhtml2pdf import pisa
import logging
import json
from django.contrib.auth.decorators import login_required
from .apis import queue_sms, process_sms_queue, check_missing_templates, create_default_templates
from core.PurchaseModel import Purchase
from core.decorators.decorators import role_required
from core.CustomerModel import Customer
from core._models import CargoProduct
import re
from django.db import connection
logger = logging.getLogger("sms_api_views")

def mask_phone_number(phone_number):
    """
    مخفی کردن شماره تلفن - فقط 3 رقم اول و 3 رقم آخر نمایش داده می‌شود
    مثال: 09123456789 -> 091*****789
    """
    if not phone_number:
        return ''
    
    phone_str = str(phone_number).strip()
    if len(phone_str) < 6:
        return phone_str
    
    return phone_str[:3] + '*' * (len(phone_str) - 6) + phone_str[-3:]

def process_template_for_customer(message, customer, purchase=None):
    """
    پردازش قالب پیامک با داده‌های مشتری
    """
    processed_message = message
    
    # داده‌های پایه مشتری
    replacements = {
        '{{customer_name}}': customer.name or '',
        '{{customer_phone}}': mask_phone_number(customer.get_primary_phone()),
    }
    
    # داده‌های کارشناس فروش
    if hasattr(customer, 'sales_agent') and customer.sales_agent.exists():
        sales_agents = customer.sales_agent.all()
        agent_names = [agent.name for agent in sales_agents if hasattr(agent, 'name') and agent.name]
        replacements['{{sales_agent_name}}'] = ', '.join(agent_names) if agent_names else ''
    else:
        replacements['{{sales_agent_name}}'] = ''
    
    # داده‌های خرید
    if purchase:
        # استفاده از خرید انتخاب شده
        selected_purchase = purchase
    elif hasattr(customer, 'purchases_made') and customer.purchases_made.exists():
        # استفاده از آخرین خرید اگر خرید خاصی انتخاب نشده باشد
        selected_purchase = customer.purchases_made.order_by('-created_at').first()
    else:
        selected_purchase = None
    
    if selected_purchase:
        replacements.update({
            '{{purchase_number}}': str(selected_purchase.purchase_number or ''),
            '{{invoice_id}}': str(selected_purchase.invoice_id or ''),
            '{{order_weight}}': str(selected_purchase.order_weight or ''),
            '{{customer_price}}': str(selected_purchase.customer_price or ''),
            '{{amount_paid}}': str(selected_purchase.amount_paid or ''),
            '{{status_display}}': str(selected_purchase.get_state_display() if hasattr(selected_purchase, 'get_state_display') else ''),
            '{{created_at}}': str(selected_purchase.created_at.strftime('%Y/%m/%d %H:%M') if selected_purchase.created_at else ''),
        })
        
        # داده‌های محصول
        if hasattr(selected_purchase, 'cargo') and selected_purchase.cargo:
            cargo = selected_purchase.cargo
            replacements.update({
                '{{cottage}}': str(cargo.cottage or ''),
                '{{product_type}}': str(cargo.get_product_type_display() if hasattr(cargo, 'get_product_type_display') else ''),
                '{{product_country}}': str(cargo.get_country_display() if hasattr(cargo, 'get_country_display') else ''),
            })
    
    # جایگزینی همه متغیرها
    for placeholder, value in replacements.items():
        processed_message = processed_message.replace(placeholder, str(value))
    
    return processed_message

@role_required('admin', 'support_agent')
@login_required
def preview_template_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            customer_purchases = data.get('customer_purchases', {})  # {customer_id: purchase_id}
            processed_messages = []
            
            for customer_id, purchase_id in customer_purchases.items():
                try:
                    customer = Customer.objects.get(id=customer_id)
                    purchase = None
                    
                    if purchase_id:
                        purchase = Purchase.objects.get(id=purchase_id, customer=customer)
                    
                    processed_message = process_template_for_customer(message, customer, purchase)
                    processed_messages.append({
                        'customer_name': customer.name,
                        'customer_phone': mask_phone_number(customer.get_primary_phone()),
                        'processed_message': processed_message
                    })
                except (Customer.DoesNotExist, Purchase.DoesNotExist):
                    continue
                
                    
            return JsonResponse({'success': True, 'processed_messages': processed_messages})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@role_required('admin', 'support_agent')
@login_required
def sms_dashboard(request):
    """داشبورد مدیریت پیامک‌ها"""
    # آمار وضعیت‌های مختلف پیامک
    pending_count = SmsQueue.objects.filter(status='pending').count()
    sent_count = SmsQueue.objects.filter(status='sent').count() 
    failed_count = SmsQueue.objects.filter(status='failed').count()
    suspended_count = SmsQueue.objects.filter(status='suspended').count()
    
    # آخرین پیامک‌های ارسال شده
    recent_sms = SmsLog.objects.all().order_by('-sent_at')[:5]
    
    context = {
        'pending_count': pending_count,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'suspended_count': suspended_count,
        'recent_sms': recent_sms,
    }
    
    return render(request, 'sms_api/sms_dashboard.html', context)


@role_required('admin', 'support_agent')
@login_required
def support_customer_search(request):
    """جستجوی زنده مشتریان برای داشبورد پشتیبانی"""
    query = request.GET.get('query', '')
    logger.info(f"Support customer search query: {query}")
    results = []
    
    if query:
        try:
            # تبدیل اعداد فارسی به انگلیسی
            persian_digits = "۰۱۲۳۴۵۶۷۸۹"
            english_digits = "0123456789"
            translation_table = str.maketrans(persian_digits, english_digits)
            query = query.translate(translation_table)
            
            # بررسی اینکه آیا جستجو بر اساس شماره تلفن است یا نام
            is_phone_search = query.isdigit()
            
            if is_phone_search:
                # جستجوی دقیق بر اساس شماره تلفن
                clean_query = query
                if clean_query.startswith('0'):
                    clean_query = clean_query[1:]
                
                customers = Customer.objects.filter(
                    Q(phone_numbers__number=clean_query) |
                    Q(phone_number=clean_query)
                ).distinct()[:10]
            else:
                # جستجوی نام با contains
                customers = Customer.objects.filter(
                    Q(name__icontains=query)
                ).distinct()[:10]
            
            results = []
            for customer in customers:
                customer_info = {
                    'id': customer.id,
                    'name': customer.name if customer.name else 'بدون نام',
                    'phone_number': mask_phone_number(customer.get_primary_phone()),
                    'city': customer.city or '',
                }
                results.append(customer_info)
                
        except Exception as e:
            logger.error(f"Error during customer search: {e}")
            results = []
    
    return JsonResponse(results, safe=False)


@role_required('admin', 'support_agent')
@login_required
def support_dashboard(request):
    """داشبورد کارشناسان پشتیبانی برای ارسال پیامک به چندین مشتری"""
    
    # دریافت قالب‌های موجود
    marketing_templates = SmsTemplate.objects.filter(template_type='marketing').order_by('-is_active', '-updated_at')
    product_templates = SmsTemplate.objects.filter(template_type='product').order_by('-is_active', '-updated_at')
    
    # تبدیل قالب‌ها به JSON برای JavaScript
    marketing_templates_list = []
    for template in marketing_templates:
        marketing_templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_active': template.is_active
        })
    marketing_templates_json = json.dumps(marketing_templates_list)
    
    product_templates_list = []
    for template in product_templates:
        product_templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_active': template.is_active
        })
    product_templates_json = json.dumps(product_templates_list)
    
    # پردازش جستجوی مشتریان (حالا فقط برای نمایش مشتریان انتخاب شده از قبل)
    search_query = request.GET.get('search', '')
    selected_customers = request.GET.getlist('customers')
    
    customers = []
    selected_customer_objects = []
    
    if selected_customers:
        # دریافت مشتریان انتخاب شده
        selected_customer_objects = Customer.objects.filter(id__in=selected_customers)
    
    # پردازش ارسال پیامک
    if request.method == 'POST':
        try:
            message = request.POST.get('message')
            selected_customers_data = request.POST.get('selected_customers_data', '')
            selected_purchases_data = request.POST.get('selected_purchases_data', '')
            notification_type = request.POST.get('notification_type', 'SUPPORT')
            
            # پردازش مشتریان انتخاب شده
            selected_customer_ids = []
            if selected_customers_data:
                try:
                    selected_customer_ids = json.loads(selected_customers_data)
                except json.JSONDecodeError:
                    # اگر JSON نامعتبر بود، از روش قدیمی استفاده می‌کنیم
                    selected_customer_ids = request.POST.getlist('selected_customers')
            
            # پردازش خریدهای انتخاب شده
            selected_purchases = {}
            if selected_purchases_data:
                try:
                    selected_purchases = json.loads(selected_purchases_data)
                except json.JSONDecodeError:
                    selected_purchases = {}
            
            # اعتبارسنجی
            if not message:
                messages.error(request, 'متن پیام نمی‌تواند خالی باشد.')
                return redirect('sms_api:support_dashboard')
            
            if not selected_customer_ids:
                messages.error(request, 'لطفاً حداقل یک مشتری را انتخاب کنید.')
                return redirect('sms_api:support_dashboard')
            
            # دریافت مشتریان انتخاب شده
            selected_customers = Customer.objects.filter(id__in=selected_customer_ids)
            
            if not selected_customers.exists():
                messages.error(request, 'هیچ مشتری معتبری انتخاب نشده است.')
                return redirect('sms_api:support_dashboard')
            
            # ارسال پیامک به همه مشتریان انتخاب شده
            total_sent = 0
            total_failed = 0
            
            for customer in selected_customers:
                # دریافت همه شماره‌های تلفن مشتری که پیامک فعال دارند
                phone_numbers = customer.get_all_phone_numbers()
                
                if not phone_numbers:
                    logger.warning(f"هیچ شماره تلفن فعالی برای مشتری {customer.name} یافت نشد.")
                    total_failed += 1
                    continue
                
                # دریافت خرید انتخاب شده برای این مشتری
                purchase = None
                if str(customer.id) in selected_purchases and selected_purchases[str(customer.id)]:
                    try:
                        purchase = Purchase.objects.get(id=selected_purchases[str(customer.id)], customer=customer)
                    except Purchase.DoesNotExist:
                        logger.warning(f"خرید انتخاب شده برای مشتری {customer.name} یافت نشد.")
                
                # پردازش قالب با داده‌های مشتری و خرید انتخاب شده
                processed_message = process_template_for_customer(message, customer, purchase)
                
                # ارسال پیامک به همه شماره‌های مشتری
                customer_sent = 0
                for phone in phone_numbers:
                    try:
                        sms = queue_sms(
                            number=phone,
                            message=processed_message,
                            notification_type=notification_type
                        )
                        customer_sent += 1
                        total_sent += 1
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیامک به شماره {phone} برای مشتری {customer.name}: {str(e)}")
                        total_failed += 1
                
                if customer_sent == 0:
                    total_failed += 1
            
            # نمایش پیام موفقیت
            if total_sent > 0:
                messages.success(
                    request, 
                    f'پیامک با موفقیت به {total_sent} شماره ارسال شد. '
                    f'{total_failed} شماره ناموفق بود.'
                )
                return redirect('sms_api:sms_dashboard')
            else:
                messages.error(request, 'هیچ پیامکی با موفقیت ارسال نشد.')
                
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ارسال پیامک: {str(e)}")
            messages.error(request, 'خطای غیرمنتظره رخ داد. لطفا دوباره تلاش کنید.')
    
    context = {
        'search_query': search_query,
        'customers': customers,
        'selected_customers': selected_customer_objects,
        'marketing_templates': marketing_templates_json,
        'product_templates': product_templates_json,
        'notification_types': SmsQueue.NOTIFICATION_TYPES,
    }
    
    return render(request, 'sms_api/support_dashboard.html', context)


@role_required('admin')
@login_required
def sms_queue(request):
    """مشاهده صف پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    
    # فیلتر کردن داده‌ها
    queue_items = SmsQueue.objects.all()
    
    if status:
        queue_items = queue_items.filter(status=status)
    
    if notification_type:
        queue_items = queue_items.filter(notification_type=notification_type)
    
    if search:
        queue_items = queue_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    # مرتب‌سازی
    queue_items = queue_items.order_by('-created_at')
    
    # صفحه‌بندی
    paginator = Paginator(queue_items, 12)  # 12 آیتم در هر صفحه
    page_number = request.GET.get('page', 1)
    queue_items = paginator.get_page(page_number)
    
    # تعداد پیامک‌ها با وضعیت‌های مختلف
    pending_count = SmsQueue.objects.filter(status='pending').count()
    sent_count = SmsQueue.objects.filter(status='sent').count()
    failed_count = SmsQueue.objects.filter(status='failed').count()
    suspended_count = SmsQueue.objects.filter(status='suspended').count()
    
    context = {
        'queue_items': queue_items,
        'status': status,
        'notification_type': notification_type,
        'search': search,
        'pending_count': pending_count,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'suspended_count': suspended_count,
        'notification_types': SmsQueue.NOTIFICATION_TYPES,
    }
    
    return render(request, 'sms_api/sms_queue.html', context)


@role_required('admin')
@login_required
def sms_log(request):
    """مشاهده تاریخچه پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # فیلتر کردن داده‌ها
    log_items = SmsLog.objects.all()
    
    if status:
        log_items = log_items.filter(status=status)
    
    if notification_type:
        log_items = log_items.filter(notification_type=notification_type)
    
    if search:
        log_items = log_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # مرتب‌سازی
    log_items = log_items.order_by('-sent_at')
    
    # صفحه‌بندی
    paginator = Paginator(log_items, 20)  # 20 آیتم در هر صفحه
    page_number = request.GET.get('page', 1)
    log_items = paginator.get_page(page_number)
    
    # آمار
    total_count = SmsLog.objects.count()
    sent_count = SmsLog.objects.filter(status='sent').count()
    failed_count = SmsLog.objects.filter(status='failed').count()
    today = timezone.now().date()
    today_count = SmsLog.objects.filter(sent_at__date=today).count()
    
    # انواع اطلاع‌رسانی برای فیلتر
    notification_types = SmsQueue.NOTIFICATION_TYPES
    
    context = {
        'log_items': log_items,
        'status': status,
        'notification_type': notification_type,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'today_count': today_count,
        'notification_types': notification_types,
    }
    
    return render(request, 'sms_api/sms_log.html', context)


def get_default_templates():
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
        'BARNAMEH_ISSUED': '{{customer_name}} عزیز؛\nبارنامه خرید {{purchase_number}} ،{{product_type}} به وزن {{order_weight}} :\nشماره بارنامه: {{barnameh}}\nتاریخ بارنامه: {{barnameh_date|default:"نامشخص"}}\nشماره راننده: {{driver_phone|default:"نامشخص"}}\nنام راننده: {{driver_name|default:"نامشخص"}}\n۰۲۱-۶۶۵۶۲۲۱۶ ☎️\nشرکت تامین نهاده سیمرغ',
        'PURCHASE_CLOSED': 'مشتری گرامی\nبارنامه خرید شما به شماره {{purchase_number}} ،{{product_type}} به وزن خرید {{order_weight}} در بازارگاه ثبت گردید.✅\nاز خرید و اعتماد شما صمیمانه سپاسگزاریم 💚\nامیدواریم در آینده نزدیک مجددا در خدمت شما باشیم 🙏\nکارشناس فروش شما: {{sales_agent_name}}\n{{sales_agent_phone}}\n۰۲۱-۶۶۵۶۲۲۱۶ داخلی {{dakheli_number|default:"۳"}}\nشرکت تامین نهاده سیمرغ',
        'DIFFERENCE_APPROVED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} با اختلاف وزن ({{extelaf_type}}) به میزان {{extelaf_weight}} کیلوگرم تحویل شده است. مبلغ قابل پرداخت: {{extelaf_amount}} ریال',
        'FULLY_SETTLED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} به صورت کامل تسویه شد.',
        'INVOICE_ISSUED': 'مشتری گرامی {{customer_name}}، \nفاکتور خرید شما با شماره {{purchase_number}} صادر شد.',
        'CANCELED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} لغو شده است. لطفا با کارشناس فروش تماس بگیرید.',
        'ARCHIVED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} آرشیو شده است.',
    }

@role_required('admin', 'support_agent')
@login_required
def create_sms(request):
    notification_types = dict(SmsQueue.NOTIFICATION_TYPES)
    
    # Get purchase templates from SmsTemplate model
    templates_dict = {}
    
    # Get all purchase templates for each status from the database
    status_templates = {}
    purchase_templates = SmsTemplate.objects.filter(template_type='purchase')
    
    # Group templates by status
    for template in purchase_templates:
        if template.status and template.status not in status_templates:
            status_templates[template.status] = []
        if template.status:
            status_templates[template.status].append(template)
    
    # For each status, use the active template if available
    for status, templates in status_templates.items():
        # Try to find an active template first
        active_templates = [t for t in templates if t.is_active]
        if active_templates:
            templates_dict[status] = active_templates[0].content
        # Otherwise use the most recently updated template
        elif templates:
            # Sort by updated_at descending
            templates.sort(key=lambda x: x.updated_at, reverse=True)
            templates_dict[status] = templates[0].content
    
    # Check if we're missing templates for any statuses and add placeholders
    # This will encourage users to create templates for missing statuses
    for status_code, _ in Purchase.STATUS_CHOICES:
        if status_code not in templates_dict:
            # Add a placeholder to indicate a template should be created
            templates_dict[status_code] = ""
    
    # Convert templates to JSON for JavaScript
    templates_json = json.dumps(templates_dict)
    
    # Get marketing templates (all templates, not just active ones)
    marketing_templates = SmsTemplate.objects.filter(template_type='marketing').order_by('-is_default', '-updated_at')
    marketing_templates_list = []
    for template in marketing_templates:
        marketing_templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_default': template.is_default,
            'is_active': template.is_active
        })
    marketing_templates_json = json.dumps(marketing_templates_list)
    
    # Get product templates (all templates, not just active ones)
    product_templates = SmsTemplate.objects.filter(template_type='product').order_by('-is_default', '-updated_at')
    product_templates_list = []
    for template in product_templates:
        product_templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_default': template.is_default,
            'is_active': template.is_active
        })
    product_templates_json = json.dumps(product_templates_list)
    
    # Create a dictionary of status display names
    purchase_statuses = {}
    for status_code, status_name in Purchase.STATUS_CHOICES:
        purchase_statuses[status_code] = status_name
    purchase_statuses_json = json.dumps(purchase_statuses)
    
    # Get all active cargo products for product selection modal
    from core._models import CargoProduct
    cargo_products = CargoProduct.objects.all().order_by('-created_at')
    
    # Handle customer search
    search_query = request.GET.get('search', '')
    selected_customer_id = request.GET.get('customer_id', '')
    
    customers = []
    purchases = []
    
    # If search was performed or customer was selected
    if search_query:
        customers = Customer.objects.filter(
            Q(name__icontains=search_query) | 
            Q(phone_numbers__number__icontains=search_query)
        ).distinct()[:10]  # محدود به 10 نتیجه
        
    if selected_customer_id:
        try:
            selected_customer = Customer.objects.get(pk=selected_customer_id)
            purchases = Purchase.objects.filter(customer=selected_customer).order_by('-created_at')[:10]
        except Customer.DoesNotExist:
            messages.error(request, 'مشتری انتخاب شده یافت نشد.')
    
    # Handle form submission
    if request.method == 'POST':
        try:
            sms_type = request.POST.get('sms_type')
            message = request.POST.get('message')
            notification_type = request.POST.get('notification_type', 'custom')
            scheduled_for_str = request.POST.get('scheduled_for')
            
            # اعتبارسنجی پیام
            if not message:
                messages.error(request, 'متن پیام نمی‌تواند خالی باشد.')
                return redirect('sms_api:create_sms')
            
            # پردازش زمان ارسال
            scheduled_for = None
            if scheduled_for_str:
                try:
                    scheduled_for = timezone.make_aware(timezone.datetime.strptime(scheduled_for_str, '%Y-%m-%dT%H:%M').replace(tzinfo=None))
                except ValueError:
                    messages.error(request, 'فرمت زمان ارسال نامعتبر است.')
                    return redirect('sms_api:create_sms')
            
            # براساس نوع پیام، پردازش متفاوتی انجام می‌دهیم
            if sms_type == 'customer':
                # ارسال پیام به مشتری
                customer_id = request.POST.get('customer_id')
                message_type = request.POST.get('message_type')
                
                if not customer_id:
                    messages.error(request, 'لطفاً مشتری را انتخاب کنید.')
                    return redirect('sms_api:create_sms')
                
                try:
                    customer = Customer.objects.get(pk=customer_id)
                except Customer.DoesNotExist:
                    messages.error(request, 'مشتری انتخاب شده یافت نشد.')
                    return redirect('sms_api:create_sms')
                
                if message_type == 'purchase':
                    # پیام مرتبط با خرید
                    purchase_id = request.POST.get('purchase_id')
                    purchase = None
                    
                    if purchase_id:
                        try:
                            purchase = Purchase.objects.get(pk=purchase_id, customer=customer)
                        except Purchase.DoesNotExist:
                            messages.warning(request, 'خرید انتخاب شده یافت نشد یا متعلق به این مشتری نیست.')
                            
                    # ارسال پیامک به همه شماره‌های مشتری
                    success_count = 0
                    for phone in customer.get_all_phone_numbers():
                        try:
                            sms = queue_sms(
                                number=phone,
                                message=message,
                                notification_type=notification_type,
                                scheduled_for=scheduled_for,
                                purchase=purchase
                            )
                            success_count += 1
                        except Exception as e:
                            logger.error(f"خطا در ایجاد پیامک برای شماره {phone}: {str(e)}")
                            messages.error(request, f'خطا در ایجاد پیامک برای شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'پیامک با موفقیت به صف ارسال برای {success_count} شماره اضافه شد.')
                        return redirect('sms_api:sms_dashboard')
                    else:
                        messages.error(request, 'هیچ پیامکی با موفقیت به صف ارسال اضافه نشد.')
                elif message_type == 'cottage':
                    # پیام اطلاع‌رسانی کوتاژ و محصولات
                    cottage_number = request.POST.get('cottage_number')
                    product_type = request.POST.get('product_type')
                    product_country = request.POST.get('product_country')
                    selected_products_data = request.POST.get('selected_products_data')
                    
                    # پردازش محصولات انتخاب شده
                    if selected_products_data:
                        try:
                            selected_products = json.loads(selected_products_data)
                            
                            # اگر محصولاتی انتخاب شده‌اند، آن‌ها را به پیام اضافه کنیم
                            if selected_products:
                                # جایگزینی متغیرهای اولین محصول (برای سازگاری با قالب‌های قدیمی)
                                first_product = selected_products[0]
                                message = message.replace('{{cottage}}', first_product.get('cottage', ''))
                                message = message.replace('{{product_type}}', first_product.get('productType', ''))
                                message = message.replace('{{product_country}}', first_product.get('productCountry', ''))
                                message = message.replace('{{port}}', first_product.get('port', ''))
                                message = message.replace('{{weight}}', first_product.get('weight', ''))
                                
                                # اگر در پیام {{products}} وجود دارد، لیست محصولات را جایگزین کنیم
                                if '{{products}}' in message:
                                    products_text = ''
                                    for i, product in enumerate(selected_products, 1):
                                        products_text += f"{i}. {product.get('productType', '')} {product.get('productCountry', '')} "
                                        products_text += f"(کوتاژ: {product.get('cottage', '')}) - {product.get('weight', '')} کیلوگرم\n"
                                    
                                    message = message.replace('{{products}}', products_text.strip())
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"خطا در پردازش محصولات انتخاب شده: {str(e)}")
                    
                    # اگر این فیلدها در پیام استفاده شده‌اند، جایگزین می‌کنیم (برای سازگاری با قالب‌های قدیمی)
                    if cottage_number:
                        message = message.replace('{{cottage}}', cottage_number)
                        
                    if product_type:
                        message = message.replace('{{product_type}}', product_type)
                        
                    if product_country:
                        message = message.replace('{{product_country}}', product_country)
                    
                    # ارسال پیامک به همه شماره‌های مشتری
                    success_count = 0
                    for phone in customer.get_all_phone_numbers():
                        try:
                            sms = queue_sms(
                                number=phone,
                                message=message,
                                notification_type='SMS_SENT',  # نوع اطلاع‌رسانی پیش‌فرض برای کوتاژ
                                scheduled_for=scheduled_for
                            )
                            success_count += 1
                        except Exception as e:
                            logger.error(f"خطا در ایجاد پیامک برای شماره {phone}: {str(e)}")
                            messages.error(request, f'خطا در ایجاد پیامک برای شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'پیامک اطلاع‌رسانی کوتاژ با موفقیت به صف ارسال برای {success_count} شماره اضافه شد.')
                        return redirect('sms_api:sms_dashboard')
                    else:
                        messages.error(request, 'هیچ پیامکی با موفقیت به صف ارسال اضافه نشد.')
                elif message_type == 'marketing':
                    # ارسال پیام تبلیغاتی به مشتری انتخاب شده
                    # ارسال پیامک به همه شماره‌های مشتری
                    success_count = 0
                    for phone in customer.get_all_phone_numbers():
                        try:
                            sms = queue_sms(
                                number=phone,
                                message=message,
                                notification_type='MARKETING',  # نوع اطلاع‌رسانی پیش‌فرض برای تبلیغات
                                scheduled_for=scheduled_for
                            )
                            success_count += 1
                        except Exception as e:
                            logger.error(f"خطا در ایجاد پیامک برای شماره {phone}: {str(e)}")
                            messages.error(request, f'خطا در ایجاد پیامک برای شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'پیامک تبلیغاتی با موفقیت به صف ارسال برای {success_count} شماره اضافه شد.')
                        return redirect('sms_api:sms_dashboard')
                    else:
                        messages.error(request, 'هیچ پیامکی با موفقیت به صف ارسال اضافه نشد.')
            elif sms_type == 'marketing':
                # ارسال پیام تبلیغاتی به شماره دلخواه
                recipient_number = request.POST.get('recipient_number')
                
                if not recipient_number:
                    messages.error(request, 'لطفاً شماره گیرنده را وارد کنید.')
                    return redirect('sms_api:create_sms')
                
                # اعتبارسنجی شماره تلفن
                phone_regex = r'^(0|0098|\+98)?9\d{9}$'
                if not re.match(phone_regex, recipient_number):
                    messages.error(request, 'فرمت شماره تلفن نامعتبر است.')
                    return redirect('sms_api:create_sms')
                
                # استاندارد کردن فرمت شماره تلفن
                if recipient_number.startswith('+98'):
                    recipient_number = '0' + recipient_number[3:]
                elif recipient_number.startswith('0098'):
                    recipient_number = '0' + recipient_number[4:]
                
                try:
                    sms = queue_sms(
                        number=recipient_number,
                        message=message,
                        notification_type='MARKETING',  # نوع اطلاع‌رسانی پیش‌فرض برای تبلیغات
                        scheduled_for=scheduled_for
                    )
                    messages.success(request, f'پیامک تبلیغاتی با موفقیت به صف ارسال برای شماره {recipient_number} اضافه شد.')
                    return redirect('sms_api:sms_dashboard')
                except Exception as e:
                    logger.error(f"خطا در ایجاد پیامک تبلیغاتی برای شماره {recipient_number}: {str(e)}")
                    messages.error(request, f'خطا در ایجاد پیامک تبلیغاتی: {str(e)}')
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ایجاد پیامک: {str(e)}")
            messages.error(request, 'خطای غیرمنتظره رخ داد. لطفا دوباره تلاش کنید.')
    
    context = {
        'notification_types': notification_types,
        'default_templates': templates_json,
        'marketing_templates': marketing_templates_json,
        'product_templates': product_templates_json,
        'purchase_statuses': purchase_statuses_json,
        'search_query': search_query,
        'customers': customers,
        'purchases': purchases,
        'selected_customer_id': selected_customer_id,
        'cargo_products': cargo_products,
    }
    
    return render(request, 'sms_api/create_sms.html', context)


@role_required('admin')
@login_required
def edit_sms(request, sms_id):
    """ویرایش پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار یا معلق قابل ویرایش هستند
    if sms.status not in ['pending', 'suspended']:
        messages.error(request, 'فقط پیامک‌های در انتظار یا معلق قابل ویرایش هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    if request.method == 'POST':
        recipient_number = request.POST.get('recipient_number')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type')
        scheduled_for = request.POST.get('scheduled_for')
        purchase_id = request.POST.get('purchase_id')
        
        # اعتبارسنجی داده‌ها
        if not recipient_number or not message:
            messages.error(request, 'لطفاً تمامی فیلدهای ضروری را پر کنید.')
            return redirect('sms_api:edit_sms', sms_id=sms.id)
        
        # تبدیل شناسه خرید به عدد
        try:
            purchase_id = int(purchase_id) if purchase_id else None
        except ValueError:
            purchase_id = None
        
        # تبدیل زمان ارسال
        if scheduled_for:
            try:
                scheduled_for = timezone.datetime.strptime(scheduled_for, '%Y-%m-%dT%H:%M')
                scheduled_for = timezone.make_aware(scheduled_for)
            except ValueError:
                scheduled_for = timezone.now()
        else:
            scheduled_for = timezone.now()
        
        # به‌روزرسانی پیامک
        sms.recipient_number = recipient_number
        sms.message = message
        sms.notification_type = notification_type
        sms.scheduled_for = scheduled_for
        sms.purchase_id = purchase_id
        sms.save()
        
        messages.success(request, 'پیامک با موفقیت به‌روزرسانی شد.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    # انواع اطلاع‌رسانی
    notification_types = SmsQueue.NOTIFICATION_TYPES
    
    context = {
        'sms': sms,
        'notification_types': notification_types,
        'scheduled_for': sms.scheduled_for.strftime('%Y-%m-%dT%H:%M') if sms.scheduled_for else None,
    }
    
    return render(request, 'sms_api/edit_sms.html', context)


@role_required('admin')
@login_required
@require_POST
def delete_sms(request, sms_id):
    """حذف پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار یا معلق قابل حذف هستند
    if sms.status not in ['pending', 'suspended']:
        messages.error(request, 'فقط پیامک‌های در انتظار یا معلق قابل حذف هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.delete()
    messages.success(request, 'پیامک با موفقیت حذف شد.')
    return redirect('sms_api:sms_queue')


@role_required('admin')
@login_required
@require_POST
def suspend_sms(request, sms_id):
    """تعلیق پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار قابل تعلیق هستند
    if sms.status != 'pending':
        messages.error(request, 'فقط پیامک‌های در انتظار قابل تعلیق هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.status = 'suspended'
    sms.is_suspended = True
    sms.save()
    
    messages.success(request, 'پیامک با موفقیت معلق شد.')
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
@require_POST
def resume_sms(request, sms_id):
    """از سرگیری پیامک معلق"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های معلق قابل از سرگیری هستند
    if sms.status != 'suspended':
        messages.error(request, 'فقط پیامک‌های معلق قابل از سرگیری هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.status = 'pending'
    sms.is_suspended = False
    sms.save()
    
    messages.success(request, 'پیامک با موفقیت از سرگرفته شد.')
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
@require_POST
def send_sms_now(request, sms_id):
    """ارسال فوری پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار قابل ارسال فوری هستند
    if sms.status != 'pending':
        messages.error(request, 'فقط پیامک‌های در انتظار قابل ارسال فوری هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    # اگر پیامک مرتبط با خرید است و مشتری دارد، به همه شماره‌های مشتری ارسال شود
    if sms.purchase and hasattr(sms.purchase, 'customer') and sms.purchase.customer:
        customer = sms.purchase.customer
        phone_numbers = customer.get_all_phone_numbers()
        
        if not phone_numbers:
            messages.error(request, f'هیچ شماره تلفنی برای مشتری {customer.name} یافت نشد.')
            return redirect('sms_api:sms_detail', sms_id=sms.id)
        
        success_count = 0
        for phone in phone_numbers:
            from sms_api.apis import sms_account
            result = sms_account.send_sms(phone, sms.message)
            
            if result and isinstance(result, list) and 200 in result:
                # ثبت در لاگ
                SmsLog.objects.create(
                    recipient_number=phone,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='sent',
                    purchase=sms.purchase,
                    api_response=json.dumps(result)
                )
                success_count += 1
        
        if success_count > 0:
            # به‌روزرسانی وضعیت پیامک اصلی
            sms.status = 'sent'
            sms.sent_at = timezone.now()
            sms.save()
            
            messages.success(request, f'پیامک با موفقیت به {success_count} شماره ارسال شد.')
        else:
            messages.error(request, 'ارسال پیامک ناموفق بود. لطفا دوباره تلاش کنید.')
    else:
        # ارسال به یک شماره تکی
        from sms_api.apis import sms_account
        result = sms_account.send_sms(sms.recipient_number, sms.message)
            
        # به‌روزرسانی وضعیت پیامک
        if result and isinstance(result, list) and 200 in result:
            sms.status = 'sent'
            sms.sent_at = timezone.now()
            sms.save()
            
            # ثبت در لاگ
            SmsLog.objects.create(
                recipient_number=sms.recipient_number,
                message=sms.message,
                notification_type=sms.notification_type,
                status='sent',
                purchase=sms.purchase,
                api_response=json.dumps(result)
            )
            
            messages.success(request, 'پیامک با موفقیت ارسال شد.')
        else:
            messages.error(request, 'ارسال پیامک ناموفق بود. لطفا دوباره تلاش کنید.')
            
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
@require_POST
def retry_sms(request, sms_id):
    """تلاش مجدد برای ارسال پیامک ناموفق"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های ناموفق قابل ارسال مجدد هستند
    if sms.status != 'failed':
        messages.error(request, 'فقط پیامک‌های ناموفق قابل ارسال مجدد هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.status = 'pending'
    sms.retry_count += 1
    sms.save()
    
    messages.success(request, 'پیامک برای ارسال مجدد در صف قرار گرفت.')
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
def export_sms_log_excel(request):
    """خروجی اکسل از تاریخچه پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # فیلتر کردن داده‌ها
    log_items = SmsLog.objects.all()
    
    if status:
        log_items = log_items.filter(status=status)
    
    if notification_type:
        log_items = log_items.filter(notification_type=notification_type)
    
    if search:
        log_items = log_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # مرتب‌سازی
    log_items = log_items.order_by('-sent_at')
    
    # ایجاد فایل اکسل
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    # فرمت‌ها
    header_format = workbook.add_format({'bold': True, 'bg_color': '#B2DFDB', 'border': 1})
    cell_format = workbook.add_format({'border': 1})
    date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy/mm/dd hh:mm:ss'})
    
    # سرستون‌ها
    headers = ['ردیف', 'شماره گیرنده', 'نوع اطلاع رسانی', 'تاریخ ارسال', 'وضعیت', 'متن پیام']
    
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header, header_format)
    
    # داده‌ها
    for row_num, sms in enumerate(log_items, 1):
        notification_type_display = dict(SmsQueue.NOTIFICATION_TYPES).get(sms.notification_type, sms.notification_type)
        status_display = 'ارسال شده' if sms.status == 'sent' else 'ناموفق'
        
        worksheet.write(row_num, 0, row_num, cell_format)
        worksheet.write(row_num, 1, sms.recipient_number, cell_format)
        worksheet.write(row_num, 2, notification_type_display, cell_format)
        worksheet.write(row_num, 3, sms.sent_at, date_format)
        worksheet.write(row_num, 4, status_display, cell_format)
        worksheet.write(row_num, 5, sms.message, cell_format)
    
    # تنظیم عرض ستون‌ها
    worksheet.set_column(0, 0, 8)
    worksheet.set_column(1, 1, 15)
    worksheet.set_column(2, 2, 20)
    worksheet.set_column(3, 3, 20)
    worksheet.set_column(4, 4, 12)
    worksheet.set_column(5, 5, 50)
    
    workbook.close()
    
    # تنظیم پاسخ HTTP
    output.seek(0)
    
    filename = f'sms_log_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


@role_required('admin')
@login_required
def export_sms_log_pdf(request):
    """خروجی PDF از تاریخچه پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # فیلتر کردن داده‌ها
    log_items = SmsLog.objects.all()
    
    if status:
        log_items = log_items.filter(status=status)
    
    if notification_type:
        log_items = log_items.filter(notification_type=notification_type)
    
    if search:
        log_items = log_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # مرتب‌سازی
    log_items = log_items.order_by('-sent_at')
    
    # محدود کردن تعداد نتایج برای PDF
    log_items = log_items[:200]
    
    # تهیه داده‌ها برای تمپلیت
    context = {
        'log_items': log_items,
        'title': 'گزارش پیامک‌ها',
        'date': timezone.now().strftime('%Y/%m/%d %H:%M:%S'),
    }
    
    # رندر کردن تمپلیت HTML
    template = get_template('sms_api/pdf_template.html')
    html = template.render(context)
    
    # ایجاد فایل PDF
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        filename = f'sms_log_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    
    return HttpResponse('خطا در ایجاد PDF', status=400)

@role_required('admin')
@login_required
def sms_logs(request):
    """نمایش لیست پیامک‌های ارسال شده"""
    logs = SmsLog.objects.all().order_by('-sent_at')
    return render(request, 'sms_api/sms_logs.html', {'logs': logs})

@role_required('admin')
@login_required
@require_POST
def process_sms_queue_manually(request):
    """
    اجرای دستی پردازش صف پیامک ها
    برای مواقعی که سیستم خودکار (سلری) در دسترس نیست
    """
    try:
        # اجرای پردازش صف پیامک
        results = process_sms_queue()
        
        # تعداد پیام‌های ارسال شده
        sent_count = sum(1 for r in results if r.get("status") == "sent")
        
        # تعداد پیام‌های ناموفق
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        
        if not results:
            messages.info(request, "هیچ پیامکی در صف ارسال یافت نشد.")
        else:
            messages.success(
                request, 
                f"پردازش صف با موفقیت انجام شد. {sent_count} پیام ارسال شد و {failed_count} پیام ناموفق بود."
            )
            
        # ثبت لاگ
        logger.info(f"پردازش دستی صف پیامک توسط کاربر {request.user}: {len(results)} پیامک")
        
    except Exception as e:
        messages.error(request, f"خطا در پردازش صف پیامک: {str(e)}")
        logger.error(f"خطا در پردازش دستی صف پیامک: {str(e)}")
    
    # بازگشت به صفحه قبلی
    return redirect('sms_api:sms_queue')

@role_required('admin')
@login_required
def template_list(request):
    """نمایش لیست قالب‌های پیامک"""
    # پارامترهای فیلتر
    template_type = request.GET.get('template_type', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    is_active = request.GET.get('is_active', '')
    
    # فیلتر کردن داده‌ها
    templates = SmsTemplate.objects.all()
    
    if template_type:
        templates = templates.filter(template_type=template_type)
    
    if status:
        templates = templates.filter(status=status)
    
    if search:
        templates = templates.filter(
            Q(name__icontains=search) | 
            Q(content__icontains=search) |
            Q(description__icontains=search)
        )
    
    if is_active:
        is_active_bool = is_active.lower() == 'true'
        templates = templates.filter(is_active=is_active_bool)
    
    # مرتب‌سازی
    templates = templates.order_by('-updated_at')
    
    # صفحه‌بندی
    paginator = Paginator(templates, 10)  # 10 آیتم در هر صفحه
    page_number = request.GET.get('page', 1)
    templates = paginator.get_page(page_number)
    
    # آمار
    total_count = SmsTemplate.objects.count()
    purchase_count = SmsTemplate.objects.filter(template_type='purchase').count()
    marketing_count = SmsTemplate.objects.filter(template_type='marketing').count()
    product_count = SmsTemplate.objects.filter(template_type='product').count()
    default_count = SmsTemplate.objects.filter(is_active=True).count()
    
    context = {
        'templates': templates,
        'template_type_filter': template_type,
        'status_filter': status,
        'search': search,
        'is_active': is_active,
        'total_count': total_count,
        'purchase_count': purchase_count,
        'marketing_count': marketing_count,
        'product_count': product_count,
        'default_count': default_count,
        'template_type_choices': SmsTemplate.TEMPLATE_TYPE_CHOICES,
        'status_choices': SmsTemplate.STATUS_CHOICES,
        'placeholders': SmsTemplate.get_available_placeholders()
    }
    
    return render(request, 'sms_api/template_list.html', context)

@role_required('admin')
@login_required
def template_create(request):
    """ایجاد قالب پیامک جدید"""
    # دریافت متن‌های پیش‌فرض برای قالب‌های مختلف
    default_templates_dict = get_default_templates()
    
    # دریافت مقدار پیش‌فرض برای وضعیت انتخاب شده
    preselected_status = request.GET.get('status', '')
    preselected_type = request.GET.get('type', 'purchase')
    default_content = ''
    
    # اگر وضعیتی در پارامترهای URL ارسال شده، محتوای پیش‌فرض آن را دریافت می‌کنیم
    if preselected_status and preselected_status in default_templates_dict:
        default_content = default_templates_dict[preselected_status]
    
    if request.method == 'POST':
        name = request.POST.get('name')
        template_type = request.POST.get('template_type', 'purchase')
        status = request.POST.get('status')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        # اعتبارسنجی
        if not name or not content:
            messages.error(request, 'لطفاً نام قالب و متن قالب را پر کنید.')
            return redirect('sms_api:template_create')
        
        if template_type == 'purchase' and not status:
            messages.error(request, 'برای قالب‌های مربوط به خرید، انتخاب وضعیت الزامی است.')
            return redirect('sms_api:template_create')
        
        try:
            template = SmsTemplate.objects.create(
                name=name,
                template_type=template_type,
                status=status if template_type == 'purchase' else None,
                content=content,
                description=description,
                is_active=is_active
            )
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را غیرفعال می‌کنیم
            if is_active:
                if template_type == 'purchase' and status:
                    SmsTemplate.objects.filter(template_type='purchase', status=status, is_active=True).exclude(id=template.id).update(is_active=False)
                else:
                    SmsTemplate.objects.filter(template_type=template_type, is_active=True).exclude(id=template.id).update(is_active=False)
                
            messages.success(request, f'قالب "{template.name}" با موفقیت ایجاد شد.')
            return redirect('sms_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد قالب: {str(e)}')
            
    context = {
        'template_type_choices': SmsTemplate.TEMPLATE_TYPE_CHOICES,
        'status_choices': SmsTemplate.STATUS_CHOICES,
        'placeholders': SmsTemplate.get_available_placeholders(),
        'default_templates': json.dumps(default_templates_dict),
        'preselected_status': preselected_status,
        'preselected_type': preselected_type,
        'default_content': default_content
    }
    
    return render(request, 'sms_api/template_create.html', context)

@role_required('admin')
@login_required
def template_edit(request, template_id):
    """ویرایش قالب پیامک"""
    template = get_object_or_404(SmsTemplate, id=template_id)
    default_templates_dict = get_default_templates()
    
    if request.method == 'POST':
        name = request.POST.get('name')
        template_type = request.POST.get('template_type', template.template_type)
        status = request.POST.get('status')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        # اعتبارسنجی
        if not name or not content:
            messages.error(request, 'لطفاً نام قالب و متن قالب را پر کنید.')
            return redirect('sms_api:template_edit', template_id=template_id)
        
        if template_type == 'purchase' and not status:
            messages.error(request, 'برای قالب‌های مربوط به خرید، انتخاب وضعیت الزامی است.')
            return redirect('sms_api:template_edit', template_id=template_id)
        
        try:
            # ذخیره مقادیر جدید
            template.name = name
            template.template_type = template_type
            template.status = status if template_type == 'purchase' else None
            template.content = content
            template.description = description
            template.is_active = is_active
            template.save()
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را غیرفعال می‌کنیم
            if is_active:
                if template_type == 'purchase' and status:
                    SmsTemplate.objects.filter(template_type='purchase', status=status, is_active=True).exclude(id=template.id).update(is_active=False)
                else:
                    SmsTemplate.objects.filter(template_type=template_type, is_active=True).exclude(id=template.id).update(is_active=False)
            
            messages.success(request, f'قالب "{template.name}" با موفقیت بروزرسانی شد.')
            return redirect('sms_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در بروزرسانی قالب: {str(e)}')
    
    # پیدا کردن متن پیش‌فرض برای این وضعیت (اگر موجود باشد)
    default_content = default_templates_dict.get(template.status, '') if template.status else ''
    
    context = {
        'template': template,
        'template_type_choices': SmsTemplate.TEMPLATE_TYPE_CHOICES,
        'status_choices': SmsTemplate.STATUS_CHOICES,
        'placeholders': SmsTemplate.get_available_placeholders(),
        'default_templates': json.dumps(default_templates_dict),
        'default_content': default_content,
    }
    
    return render(request, 'sms_api/template_edit.html', context)

@role_required('admin')
@login_required
def template_detail(request, template_id):
    """مشاهده جزئیات قالب پیامک"""
    template = get_object_or_404(SmsTemplate, id=template_id)
    
    context = {
        'template': template,
        'placeholders': SmsTemplate.get_available_placeholders()
    }
    
    return render(request, 'sms_api/template_detail.html', context)

@role_required('admin')
@login_required
@require_POST
def template_delete(request, template_id):
    """حذف قالب پیامک"""
    template = get_object_or_404(SmsTemplate, id=template_id)
    
    # اگر قالب پیش‌فرض است و قالب دیگری از این نوع وجود ندارد، اجازه حذف نمی‌دهیم
    if template.is_active and SmsTemplate.objects.filter(status=template.status).count() == 1:
        messages.error(request, 'نمی‌توانید تنها قالب پیش‌فرض یک وضعیت را حذف کنید.')
        return redirect('sms_api:template_list')
    
    try:
        template_name = template.name
        template.delete()
        messages.success(request, f'قالب "{template_name}" با موفقیت حذف شد.')
    except Exception as e:
        messages.error(request, f'خطا در حذف قالب: {str(e)}')
    
    return redirect('sms_api:template_list')

@role_required('admin')
@login_required
@require_POST
def set_template_default(request, template_id):
    """تنظیم قالب به عنوان پیش‌فرض"""
    template = get_object_or_404(SmsTemplate, id=template_id)
    
    try:
        # قالب‌های پیش‌فرض دیگر را غیرفعال می‌کنیم
        if template.template_type == 'purchase' and template.status:
            SmsTemplate.objects.filter(template_type='purchase', status=template.status, is_active=True).update(is_active=False)
        else:
            SmsTemplate.objects.filter(template_type=template.template_type, is_active=True).update(is_active=False)
        
        # این قالب را پیش‌فرض می‌کنیم
        template.is_active = True
        template.save()
        
        if template.template_type == 'purchase' and template.status:
            messages.success(request, f'قالب "{template.name}" به عنوان پیش‌فرض برای وضعیت "{template.get_status_display()}" تنظیم شد.')
        else:
            messages.success(request, f'قالب "{template.name}" به عنوان پیش‌فرض برای نوع "{template.get_template_type_display()}" تنظیم شد.')
    except Exception as e:
        messages.error(request, f'خطا در تنظیم قالب پیش‌فرض: {str(e)}')
    
    return redirect('sms_api:template_list')

@role_required('admin')
@login_required
def template_preview(request, template_id):
    """پیش‌نمایش قالب با داده‌های آزمایشی"""
    template = get_object_or_404(SmsTemplate, id=template_id)
    
    # داده‌های آزمایشی برای پیش‌نمایش - با فرمت ساختاری
    sample_data = {
        'customer.name': 'مشتری نمونه',
        'purchase.purchase_number': '1234567',
        'purchase.invoice_id': '12345',
        'purchase.order_weight': '25000',
        'purchase.customer_price': '150000',
        'purchase.amount_paid': '3750000000',
        'purchase.barnameh': 'B-987654',
        'purchase.extelaf_weight': '500',
        'purchase.extelaf_amount': '75000000',
        'cargo.cottage': '12345678',
        'cargo.product_type': 'ذرت',
        'cargo.country': 'برزیل',
        'customer.sales_agent.phone_number': '09123456789',
        'customer.sales_agent.name': 'کارشناس فروش نمونه',
        'purchase.shenase_takhsis': 'ABC123456789',
    }
    
    # پردازش قالب
    preview_text = template.content
    for key, value in sample_data.items():
        # ایجاد الگوی جستجو با در نظر گرفتن فضای خالی احتمالی
        pattern = r'{{\s*' + re.escape(key) + r'\s*}}'
        preview_text = re.sub(pattern, value, preview_text)
    
    context = {
        'template': template,
        'preview_text': preview_text,
        'sample_data': sample_data
    }
    
    return render(request, 'sms_api/template_preview.html', context)

@role_required('admin')
@login_required
def template_test(request, template_id):
    """ارسال پیامک آزمایشی با استفاده از قالب"""
    template = get_object_or_404(SmsTemplate, id=template_id)
    
    if request.method == 'POST':
        recipient_number = request.POST.get('recipient_number')
        
        if not recipient_number:
            messages.error(request, 'لطفاً شماره تلفن را وارد کنید.')
            return redirect('sms_api:template_test', template_id=template_id)
        
        try:
            # داده‌های آزمایشی برای پردازش قالب - با فرمت ساختاری
            sample_data = {
                'customer.name': 'مشتری نمونه',
                'purchase.purchase_number': '1234567',
                'purchase.invoice_id': '12345',
                'purchase.order_weight': '25000',
                'purchase.customer_price': '150000',
                'purchase.amount_paid': '3750000000',
                'purchase.barnameh': 'B-987654',
                'purchase.extelaf_weight': '500',
                'purchase.extelaf_amount': '75000000',
                'cargo.cottage': '12345678',
                'cargo.product_type': 'ذرت',
                'cargo.country': 'برزیل',
                'customer.sales_agent.phone_number': '09123456789',
                'customer.sales_agent.name': 'کارشناس فروش نمونه',
                'purchase.shenase_takhsis': 'ABC123456789',
            }
            
            # پردازش قالب
            message_text = template.content
            for key, value in sample_data.items():
                # ایجاد الگوی جستجو با در نظر گرفتن فضای خالی احتمالی
                pattern = r'{{\s*' + re.escape(key) + r'\s*}}'
                message_text = re.sub(pattern, value, message_text)
            
            # ارسال پیامک
            queue_sms(recipient_number, message_text, notification_type='custom')
            
            messages.success(request, f'پیامک آزمایشی به شماره {recipient_number} ارسال شد.')
            return redirect('sms_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در ارسال پیامک آزمایشی: {str(e)}')
    
    context = {
        'template': template
    }
    
    return render(request, 'sms_api/template_test.html', context)

@role_required('admin')
@login_required
def template_check(request):
    """نمایش وضعیت قالب‌های پیامک و ایجاد قالب‌های پیش‌فرض"""
    # Check for missing templates
    missing_templates = check_missing_templates()
    
    # If form submitted, create missing templates
    if request.method == 'POST':
        replace_existing = request.POST.get('replace_existing', 'off') == 'on'
        created, updated, skipped = create_default_templates(replace_existing)
        
        if created > 0:
            messages.success(request, f"{created} قالب جدید با موفقیت ایجاد شد.")
        if updated > 0:
            messages.success(request, f"{updated} قالب موجود به‌روزرسانی شد.")
        if skipped > 0:
            messages.info(request, f"{skipped} قالب موجود بدون تغییر باقی ماند.")
            
        # Redirect to avoid resubmission
        return redirect('sms_api:template_check')
    
    context = {
        'missing_templates': missing_templates,
        'missing_count': len(missing_templates),
        'all_statuses_count': len([status[0] for status in Purchase.STATUS_CHOICES]),
    }
    
    return render(request, 'sms_api/template_check.html', context)

@role_required('admin', 'support_agent')
@login_required
def get_templates_for_status(request):
    """Returns all templates for a specific status as JSON"""
    status = request.GET.get('status', '')
    
    if not status:
        return JsonResponse({'error': 'Status parameter is required'}, status=400)
    
    # Get all purchase templates for the specified status
    templates = SmsTemplate.objects.filter(template_type='purchase', status=status).order_by('-is_active', '-updated_at')
    
    # Convert templates to a list of dicts for JSON serialization
    templates_list = []
    for template in templates:
        templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_active': template.is_active,
            'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return JsonResponse({
        'status': status,
        'status_display': dict(Purchase.STATUS_CHOICES).get(status, status),
        'templates': templates_list,
        'count': len(templates_list)
    })

@role_required('admin', 'support_agent')
@login_required
def get_marketing_templates(request):
    """Returns all marketing templates as JSON"""
    # Get all marketing templates
    templates = SmsTemplate.objects.filter(template_type='marketing').order_by('-is_active', '-updated_at')
    
    # Convert templates to a list of dicts for JSON serialization
    templates_list = []
    for template in templates:
        templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_active': template.is_active,
            'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return JsonResponse({
        'templates': templates_list,
        'count': len(templates_list)
    })

@role_required('admin', 'support_agent')
@login_required
def get_product_templates(request):
    """Returns all product templates as JSON"""
    # Get all product templates
    templates = SmsTemplate.objects.filter(template_type='product').order_by('-is_active', '-updated_at')
    
    # Convert templates to a list of dicts for JSON serialization
    templates_list = []
    for template in templates:
        templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_active': template.is_active,
            'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return JsonResponse({
        'templates': templates_list,
        'count': len(templates_list)
    })

@role_required('admin', 'support_agent')
@login_required
def get_customer_purchases(request):
    """Returns all purchases for a specific customer as JSON"""
    customer_id = request.GET.get('customer_id')
    
    if not customer_id:
        return JsonResponse({'error': 'Customer ID is required'}, status=400)
    
    try:
        customer = Customer.objects.get(id=customer_id)
        purchases = customer.purchases_made.all().order_by('-created_at')
        
        purchases_list = []
        for purchase in purchases:
            purchases_list.append({
                'id': purchase.id,
                'purchase_number': purchase.purchase_number or '',
                'invoice_id': purchase.invoice_id or '',
                'order_weight': purchase.order_weight or 0,
                'state': purchase.state,
                'state_display': purchase.get_state_display(),
                'created_at': purchase.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'cargo_info': f"{purchase.cargo.get_product_type_display() if purchase.cargo else ''} {purchase.cargo.get_country_display() if purchase.cargo else ''}".strip() or 'بدون محصول'
            })
        
        return JsonResponse({
            'customer_name': customer.name or 'بدون نام',
            'customer_phone': mask_phone_number(customer.get_primary_phone()),
            'purchases': purchases_list,
            'count': len(purchases_list)
        })
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)

@role_required('admin', 'support_agent')
@login_required
def sms_detail(request, sms_id):
    """نمایش جزئیات پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    logs = SmsLog.objects.filter(recipient_number=sms.recipient_number).order_by('-sent_at')
    
    context = {
        'sms': sms,
        'logs': logs
    }
    return render(request, 'sms_api/sms_detail.html', context)