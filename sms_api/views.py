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
logger = logging.getLogger(__name__)

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
        'INITIATED': 'مشتری گرامی {{customer.name}}خرید شما به شماره {{purchase.number}} ،{{product.type}} به وزن {{order.weight}} در بازارگاه به صورت نقدی ثبت گردید.✅لطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود جهت ارسال بار اقدام فرمایید.از خرید و اعتماد شما سپاسگزاریم و امیدواریم تجربه‌ای عالی برایتان رقم بزنیم 💚جهت پیگیری وضعیت سفارش خود، لطفاً با شماره ثابت دفتر (داخلی ۳) تماس بگیرید:۰۲۱-۶۶۵۶۲۲۱۶ ☎️شرکت تامین نهاده سیمرغ',
        'SMS_SENT': 'مشتری گرامی {{customer_name}}، \nکالای {{product_type}} {{product_country}} به وزن {{order_weight}} کیلوگرم و قیمت {{customer_price}} ریال برای شما ثبت شد. کوتاژ: {{cottage}}',
        'PAYMENT_VERIFIED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} در بازارگاه تایید شد. نوع کالا: {{product_type}} {{product_country}}',
        'ALLOCATION_APPROVED': 'مشتری گرامی {{customer_name}}، \nشناسه تخصیص برای خرید شما با شماره {{purchase_number}} تایید شد.',
        'ADDRESS_SENT': 'مشتری گرامی {{customer_name}}، \nآدرس ارسال برای خرید شما با شماره {{purchase_number}} به واردکننده ارسال شد.',
        'WAITING_FOR_BARNAMEH': 'مشتری گرامی {{customer_name}}، \nسفارش شما با شماره {{purchase_number}} در انتظار صدور بارنامه می‌باشد.',
        'BARNAMEH_INCOMPLETE': 'مشتری گرامی {{customer_name}}، \nبارنامه برای خرید شما با شماره {{purchase_number}} ناقص است. در حال پیگیری هستیم.',
        'BARNAMEH_ISSUED': 'مشتری گرامی {{customer_name}}، \nبارنامه برای خرید شما با شماره {{purchase_number}} صادر شد. شماره بارنامه: {{barnameh}}',
        'PURCHASE_CLOSED': 'مشتری گرامی {{customer_name}}، \nخرید شما با شماره {{purchase_number}} در بازارگاه بسته شد. از خرید شما متشکریم.',
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
    
    # Get templates from SmsTemplate model only
    templates_dict = {}
    
    # Get all templates for each status from the database
    status_templates = {}
    all_templates = SmsTemplate.objects.all()
    
    # Group templates by status
    for template in all_templates:
        if template.status not in status_templates:
            status_templates[template.status] = []
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
    
    # Create a dictionary of status display names
    purchase_statuses = {}
    for status_code, status_name in Purchase.STATUS_CHOICES:
        purchase_statuses[status_code] = status_name
    purchase_statuses_json = json.dumps(purchase_statuses)
    
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
                    
                    # اگر این فیلدها در پیام استفاده شده‌اند، جایگزین می‌کنیم
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
        'purchase_statuses': purchase_statuses_json,
        'search_query': search_query,
        'customers': customers,
        'purchases': purchases,
        'selected_customer_id': selected_customer_id,
        'cargo_products': CargoProduct.get_active_products(),
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
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    is_active = request.GET.get('is_active', '')
    
    # فیلتر کردن داده‌ها
    templates = SmsTemplate.objects.all()
    
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
    default_count = SmsTemplate.objects.filter(is_active=True).count()
    
    context = {
        'templates': templates,
        'status_filter': status,
        'search': search,
        'is_active': is_active,
        'total_count': total_count,
        'default_count': default_count,
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
    default_content = ''
    
    # اگر وضعیتی در پارامترهای URL ارسال شده، محتوای پیش‌فرض آن را دریافت می‌کنیم
    if preselected_status and preselected_status in default_templates_dict:
        default_content = default_templates_dict[preselected_status]
    
    if request.method == 'POST':
        name = request.POST.get('name')
        status = request.POST.get('status')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not status or not content:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید.')
            return redirect('sms_api:template_create')
        
        try:
            template = SmsTemplate.objects.create(
                name=name,
                status=status,
                content=content,
                description=description,
                is_active=is_active
            )
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را برای این وضعیت غیرفعال می‌کنیم
            if is_active:
                SmsTemplate.objects.filter(status=status, is_active=True).exclude(id=template.id).update(is_active=False)
                
            messages.success(request, f'قالب "{template.name}" با موفقیت ایجاد شد.')
            return redirect('sms_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد قالب: {str(e)}')
            
    context = {
        'status_choices': SmsTemplate.STATUS_CHOICES,
        'placeholders': SmsTemplate.get_available_placeholders(),
        'default_templates': json.dumps(default_templates_dict),
        'preselected_status': preselected_status,
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
        status = request.POST.get('status')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not status or not content:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید.')
            return redirect('sms_api:template_edit', template_id=template_id)
        
        try:
            # بررسی تغییر وضعیت
            status_changed = template.status != status
            
            # ذخیره مقادیر جدید
            template.name = name
            template.status = status
            template.content = content
            template.description = description
            template.is_active = is_active
            template.save()
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را برای این وضعیت غیرفعال می‌کنیم
            if is_active:
                SmsTemplate.objects.filter(status=status, is_active=True).exclude(id=template.id).update(is_active=False)
            
            messages.success(request, f'قالب "{template.name}" با موفقیت بروزرسانی شد.')
            return redirect('sms_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در بروزرسانی قالب: {str(e)}')
    
    # پیدا کردن متن پیش‌فرض برای این وضعیت (اگر موجود باشد)
    default_content = default_templates_dict.get(template.status, '')
    
    context = {
        'template': template,
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
        # قالب‌های پیش‌فرض دیگر از همین وضعیت را غیرفعال می‌کنیم
        SmsTemplate.objects.filter(status=template.status, is_active=True).update(is_active=False)
        
        # این قالب را پیش‌فرض می‌کنیم
        template.is_active = True
        template.save()
        
        messages.success(request, f'قالب "{template.name}" به عنوان پیش‌فرض برای وضعیت "{template.get_status_display()}" تنظیم شد.')
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
    
    # Get all templates for the specified status
    templates = SmsTemplate.objects.filter(status=status).order_by('-is_active', '-updated_at')
    
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
def sms_detail(request, sms_id):
    """نمایش جزئیات پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    logs = SmsLog.objects.filter(recipient_number=sms.recipient_number).order_by('-sent_at')
    
    context = {
        'sms': sms,
        'logs': logs
    }
    return render(request, 'sms_api/sms_detail.html', context)