from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import WhatsappNumber, WhatsappLog, WhatsappTemplate, WhatsappQueue
from .utils import send_whatsapp_message
from core._models import Customer
from django.db import models
from core._models import CargoProduct, Purchase
from core.decorators.decorators import role_required
import json
import logging
import re

logger = logging.getLogger(__name__)

@role_required('admin')
@login_required
def whatsapp_dashboard(request):
    """داشبورد مدیریت پیام‌های واتساپ"""
    # آمار فعالیت شماره‌های واتساپ
    active_numbers = WhatsappNumber.objects.filter(is_active=True).count()
    total_sent = WhatsappNumber.objects.aggregate(total=models.Sum('messages_sent'))['total'] or 0
    today_sent = WhatsappNumber.objects.aggregate(total=models.Sum('sent_today'))['total'] or 0
    
    # آخرین پیام‌های ارسال شده
    recent_messages = WhatsappLog.objects.all().order_by('-sent_at')[:5]
    
    context = {
        'active_numbers': active_numbers,
        'total_sent': total_sent,
        'today_sent': today_sent,
        'recent_messages': recent_messages,
    }
    
    return render(request, 'whatsapp_api/whatsapp_dashboard.html', context)

@role_required('admin')
@login_required
def send_whatsapp(request):
    notification_types = {
        'custom': 'پیام سفارشی',
        'purchase_notification': 'اطلاع‌رسانی خرید',
        'cottage_notification': 'اطلاع‌رسانی کوتاژ',
        'marketing': 'پیام تبلیغاتی'
    }
    
    # Get templates from WhatsappTemplate model
    templates_dict = {}
    
    # Get all templates for each status from the database
    status_templates = {}
    all_templates = WhatsappTemplate.objects.all()
    
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
    for status_code, _ in WhatsappTemplate.STATUS_CHOICES:
        if status_code not in templates_dict:
            # Add a placeholder to indicate a template should be created
            templates_dict[status_code] = ""
    
    # Convert templates to JSON for JavaScript
    templates_json = json.dumps(templates_dict)
    
    # Create a dictionary of status display names
    purchase_statuses = {}
    for status_code, status_name in WhatsappTemplate.STATUS_CHOICES:
        purchase_statuses[status_code] = status_name
    purchase_statuses_json = json.dumps(purchase_statuses)
    
    # Get cargo products for cottage message selection
    cargo_products = CargoProduct.objects.filter(status=True).order_by('-created_at')[:50]
    
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
            whatsapp_type = request.POST.get('whatsapp_type')
            message = request.POST.get('message')
            notification_type = request.POST.get('notification_type', 'custom')
            scheduled_for_str = request.POST.get('scheduled_for')
            template_type = request.POST.get('template_type', 'general')
            
            # اعتبارسنجی پیام
            if not message:
                messages.error(request, 'متن پیام نمی‌تواند خالی باشد.')
                return redirect('whatsapp_api:send-whatsapp')
            
            # پردازش زمان ارسال
            scheduled_for = None
            if scheduled_for_str:
                try:
                    scheduled_for = timezone.make_aware(timezone.datetime.strptime(scheduled_for_str, '%Y-%m-%dT%H:%M').replace(tzinfo=None))
                except ValueError:
                    messages.error(request, 'فرمت زمان ارسال نامعتبر است.')
                    return redirect('whatsapp_api:send-whatsapp')
            
            # براساس نوع پیام، پردازش متفاوتی انجام می‌دهیم
            if whatsapp_type == 'customer':
                # ارسال پیام به مشتری
                customer_id = request.POST.get('customer_id')
                message_type = request.POST.get('message_type')
                
                if not customer_id:
                    messages.error(request, 'لطفاً مشتری را انتخاب کنید.')
                    return redirect('whatsapp_api:send-whatsapp')
                
                try:
                    customer = Customer.objects.get(pk=customer_id)
                except Customer.DoesNotExist:
                    messages.error(request, 'مشتری انتخاب شده یافت نشد.')
                    return redirect('whatsapp_api:send-whatsapp')
                
                if message_type == 'purchase':
                    # پیام مرتبط با خرید
                    purchase_id = request.POST.get('purchase_id')
                    purchase = None
                    
                    if purchase_id:
                        try:
                            purchase = Purchase.objects.get(pk=purchase_id, customer=customer)
                        except Purchase.DoesNotExist:
                            messages.warning(request, 'خرید انتخاب شده یافت نشد یا متعلق به این مشتری نیست.')
                    
                    # دریافت قالب مناسب اگر متن پیام خالی است
                    if not message and purchase:
                        try:
                            template = WhatsappTemplate.objects.get(status=purchase.state, is_active=True)
                            message = template.content
                            template_type = template.template_type
                        except WhatsappTemplate.DoesNotExist:
                            messages.error(request, 'قالب پیامی برای این وضعیت خرید یافت نشد.')
                            return redirect('whatsapp_api:send-whatsapp')
                    
                    # ایجاد داده‌های پیام
                    message_data = {}
                    if purchase:
                        message_data = {
                            'customer_name': customer.name,
                            'purchase_number': purchase.purchase_number,
                            'invoice_id': purchase.invoice_id,
                            'order_weight': str(purchase.order_weight),
                            'customer_price': str(purchase.customer_price),
                            'amount_paid': str(purchase.amount_paid),
                            'barnameh': purchase.barnameh or '',
                            'barnameh_date': purchase.barnameh_date or '',
                            'driver_name': purchase.driver_name or '',
                            'driver_phone': purchase.driver_phone or '',
                            'shenase_takhsis': purchase.shenase_takhsis or '',
                        }
                        if hasattr(purchase, 'extelaf_weight'):
                            message_data['extelaf_weight'] = str(purchase.extelaf_weight)
                            message_data['extelaf_amount'] = str(purchase.extelaf_amount)
                            message_data['extelaf_type'] = purchase.extelaf_type
                    
                    # ارسال واتساپ به شماره اصلی مشتری
                    success_count = 0
                    try:
                        phone = customer.get_primary_phone()
                        if phone:
                            # ایجاد پیام در صف واتساپ
                            whatsapp_queue = WhatsappQueue.objects.create(
                                recipient_number=phone,
                                template_type=template_type,
                                message=message,
                                notification_type=notification_type,
                                status='pending',
                                scheduled_for=scheduled_for
                            )
                            
                            # ارسال پیام واتساپ
                            if scheduled_for is None or scheduled_for <= timezone.now():
                                success = send_whatsapp_message(phone, template_type, message_data)
                                
                                if success:
                                    whatsapp_queue.status = 'sent'
                                    whatsapp_queue.sent_at = timezone.now()
                                    whatsapp_queue.save()
                                    
                                    # ثبت در لاگ
                                    WhatsappLog.objects.create(
                                        recipient_number=phone,
                                        template_type=template_type,
                                        message=message,
                                        status='sent',
                                        sent_at=whatsapp_queue.sent_at
                                    )
                                    
                                    success_count += 1
                            else:
                                # پیام زمان‌بندی شده است
                                success_count += 1
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام واتساپ به شماره {phone}: {str(e)}")
                        messages.error(request, f'خطا در ارسال پیام واتساپ به شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        if scheduled_for and scheduled_for > timezone.now():
                            messages.success(request, f'پیام واتساپ با موفقیت زمان‌بندی شد برای ارسال در {scheduled_for}.')
                        else:
                            messages.success(request, f'پیام واتساپ با موفقیت به {customer.name} ارسال شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, f'ارسال پیام واتساپ به {customer.name} ناموفق بود.')
                
                elif message_type == 'cottage':
                    # پیام اطلاع‌رسانی کوتاژ و محصولات
                    cottage_number = request.POST.get('cottage_number')
                    product_type = request.POST.get('product_type')
                    product_country = request.POST.get('product_country')
                    selected_products_data = request.POST.get('selected_products_data', '[]')
                    
                    # پردازش داده‌های محصولات انتخاب شده
                    try:
                        selected_products = json.loads(selected_products_data)
                    except json.JSONDecodeError:
                        selected_products = []
                    
                    # اگر این فیلدها در پیام استفاده شده‌اند، جایگزین می‌کنیم
                    if cottage_number:
                        message = message.replace('{{cottage}}', cottage_number)
                        
                    if product_type:
                        message = message.replace('{{product_type}}', product_type)
                        
                    if product_country:
                        message = message.replace('{{product_country}}', product_country)
                    
                    # جایگزینی اطلاعات محصولات
                    if selected_products:
                        message = message.replace('{{product_count}}', str(len(selected_products)))
                        
                        if len(selected_products) == 1:
                            product = selected_products[0]
                            message = message.replace('{{product_name}}', product.get('name', ''))
                            message = message.replace('{{product_cottage}}', product.get('cottage', ''))
                            message = message.replace('{{product_weight}}', product.get('weight', ''))
                    
                    # ارسال واتساپ به شماره اصلی مشتری
                    success_count = 0
                    try:
                        phone = customer.get_primary_phone()
                        if phone:
                            # ایجاد پیام در صف واتساپ
                            whatsapp_queue = WhatsappQueue.objects.create(
                                recipient_number=phone,
                                template_type='cottage_notification',
                                message=message,
                                notification_type='cottage_notification',
                                status='pending',
                                scheduled_for=scheduled_for
                            )
                            
                            # ارسال پیام واتساپ
                            if scheduled_for is None or scheduled_for <= timezone.now():
                                success = send_whatsapp_message(phone, 'cottage_notification', {})
                                
                                if success:
                                    whatsapp_queue.status = 'sent'
                                    whatsapp_queue.sent_at = timezone.now()
                                    whatsapp_queue.save()
                                    
                                    # ثبت در لاگ
                                    WhatsappLog.objects.create(
                                        recipient_number=phone,
                                        template_type='cottage_notification',
                                        message=message,
                                        status='sent',
                                        sent_at=whatsapp_queue.sent_at
                                    )
                                    
                                    success_count += 1
                            else:
                                # پیام زمان‌بندی شده است
                                success_count += 1
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام واتساپ به شماره {phone}: {str(e)}")
                        messages.error(request, f'خطا در ارسال پیام واتساپ به شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        if scheduled_for and scheduled_for > timezone.now():
                            messages.success(request, f'پیام واتساپ اطلاع‌رسانی کوتاژ با موفقیت زمان‌بندی شد برای ارسال در {scheduled_for}.')
                        else:
                            messages.success(request, f'پیام واتساپ اطلاع‌رسانی کوتاژ با موفقیت به {customer.name} ارسال شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, f'ارسال پیام واتساپ اطلاع‌رسانی کوتاژ به {customer.name} ناموفق بود.')
                
                elif message_type == 'marketing':
                    # ارسال پیام تبلیغاتی به مشتری انتخاب شده
                    # ارسال واتساپ به شماره اصلی مشتری
                    success_count = 0
                    try:
                        phone = customer.get_primary_phone()
                        if phone:
                            # ایجاد پیام در صف واتساپ
                            whatsapp_queue = WhatsappQueue.objects.create(
                                recipient_number=phone,
                                template_type='marketing',
                                message=message,
                                notification_type='marketing',
                                status='pending',
                                scheduled_for=scheduled_for
                            )
                            
                            # ارسال پیام واتساپ
                            if scheduled_for is None or scheduled_for <= timezone.now():
                                success = send_whatsapp_message(phone, 'marketing', {})
                                
                                if success:
                                    whatsapp_queue.status = 'sent'
                                    whatsapp_queue.sent_at = timezone.now()
                                    whatsapp_queue.save()
                                    
                                    # ثبت در لاگ
                                    WhatsappLog.objects.create(
                                        recipient_number=phone,
                                        template_type='marketing',
                                        message=message,
                                        status='sent',
                                        sent_at=whatsapp_queue.sent_at
                                    )
                                    
                                    success_count += 1
                            else:
                                # پیام زمان‌بندی شده است
                                success_count += 1
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام واتساپ به شماره {phone}: {str(e)}")
                        messages.error(request, f'خطا در ارسال پیام واتساپ به شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        if scheduled_for and scheduled_for > timezone.now():
                            messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت زمان‌بندی شد برای ارسال در {scheduled_for}.')
                        else:
                            messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت به {customer.name} ارسال شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, f'ارسال پیام واتساپ تبلیغاتی به {customer.name} ناموفق بود.')
                
            elif whatsapp_type == 'marketing':
                # ارسال پیام تبلیغاتی به شماره دلخواه
                recipient_number = request.POST.get('recipient_number')
                
                if not recipient_number:
                    messages.error(request, 'لطفاً شماره گیرنده را وارد کنید.')
                    return redirect('whatsapp_api:send-whatsapp')
                
                # اعتبارسنجی فرمت شماره تلفن
                if not re.match(r'^(0|0098|\+98)?9\d{9}$', recipient_number):
                    messages.error(request, 'فرمت شماره تلفن وارد شده نامعتبر است.')
                    return redirect('whatsapp_api:send-whatsapp')
                
                # استاندارد کردن فرمت شماره تلفن
                if recipient_number.startswith('0098'):
                    recipient_number = '+98' + recipient_number[4:]
                elif recipient_number.startswith('0'):
                    recipient_number = '+98' + recipient_number[1:]
                elif not recipient_number.startswith('+98'):
                    recipient_number = '+98' + recipient_number
                
                # ایجاد پیام در صف واتساپ
                whatsapp_queue = WhatsappQueue.objects.create(
                    recipient_number=recipient_number,
                    template_type='marketing',
                    message=message,
                    notification_type='marketing',
                    status='pending',
                    scheduled_for=scheduled_for
                )
                
                # ارسال پیام واتساپ
                success = False
                if scheduled_for is None or scheduled_for <= timezone.now():
                    success = send_whatsapp_message(recipient_number, 'marketing', {})
                    
                    if success:
                        whatsapp_queue.status = 'sent'
                        whatsapp_queue.sent_at = timezone.now()
                        whatsapp_queue.save()
                        
                        # ثبت در لاگ
                        WhatsappLog.objects.create(
                            recipient_number=recipient_number,
                            template_type='marketing',
                            message=message,
                            status='sent',
                            sent_at=whatsapp_queue.sent_at
                        )
                        
                        if scheduled_for and scheduled_for > timezone.now():
                            messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت زمان‌بندی شد برای ارسال به {recipient_number} در {scheduled_for}.')
                        else:
                            messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت به {recipient_number} ارسال شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, f'ارسال پیام واتساپ تبلیغاتی به {recipient_number} ناموفق بود.')
                else:
                    # پیام زمان‌بندی شده است
                    messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت زمان‌بندی شد برای ارسال به {recipient_number} در {scheduled_for}.')
                    return redirect('whatsapp_api:whatsapp-dashboard')
            
        except Exception as e:
            logger.error(f"خطا در ارسال پیام واتساپ: {str(e)}")
            messages.error(request, f'خطا در ارسال پیام واتساپ: {str(e)}')
    
    context = {
        'notification_types': notification_types,
        'default_templates': templates_json,
        'purchase_statuses': purchase_statuses_json,
        'customers': customers,
        'purchases': purchases,
        'search_query': search_query,
        'selected_customer_id': selected_customer_id,
        'cargo_products': cargo_products,
        'templates': all_templates,
    }
    return render(request, 'whatsapp_api/send_whatsapp.html', context)

@role_required('admin')
@login_required
def message_history(request):
    """تاریخچه پیام‌های واتساپ"""
    template_type = request.GET.get('template_type')
    search = request.GET.get('search')
    
    logs = WhatsappLog.objects.all()
    
    if template_type:
        logs = logs.filter(template_type=template_type)
    
    if search:
        logs = logs.filter(
            Q(recipient_number__icontains=search) |
            Q(message__icontains=search)
        )
        
    logs = logs.order_by('-sent_at')
    paginator = Paginator(logs, 20)
    page = request.GET.get('page')
    logs = paginator.get_page(page)
    
    templates = WhatsappTemplate.objects.all()
    
    context = {
        'logs': logs,
        'templates': templates,
        'current_template': template_type,
        'search': search,
    }
    
    return render(request, 'whatsapp_api/message_history.html', context)

@role_required('admin')
@login_required
def templates(request):
    """مدیریت تمپلیت‌های واتساپ و افزودن تمپلیت جدید"""
    template_types = WhatsappTemplate.TEMPLATE_TYPES
    if request.method == 'POST':
        name = request.POST.get('name')
        template_type = request.POST.get('template_type')
        content = request.POST.get('content')
        is_active = request.POST.get('is_active') == 'on'
        if name and template_type and content:
            WhatsappTemplate.objects.create(
                name=name,
                template_type=template_type,
                content=content,
                is_active=is_active
            )
            messages.success(request, 'قالب جدید با موفقیت ثبت شد.')
            return redirect('whatsapp_api:templates')
        else:
            messages.error(request, 'همه فیلدها الزامی هستند.')

    templates = WhatsappTemplate.objects.all().order_by('template_type', 'name')
    context = {
        'templates': templates,
        'template_types': template_types,
    }
    return render(request, 'whatsapp_api/templates.html', context)

@role_required('admin')
@login_required
def whatsapp_queue(request):
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    queue_items = WhatsappQueue.objects.all()
    if status:
        queue_items = queue_items.filter(status=status)
    if search:
        queue_items = queue_items.filter(
            Q(recipient_number__icontains=search) | Q(message__icontains=search)
        )
    queue_items = queue_items.order_by('-created_at')
    paginator = Paginator(queue_items, 12)
    page_number = request.GET.get('page', 1)
    queue_items = paginator.get_page(page_number)
    context = {
        'queue_items': queue_items,
        'status': status,
        'search': search,
    }
    return render(request, 'whatsapp_api/whatsapp_queue.html', context)

@role_required('admin')
@login_required
def template_list(request):
    """نمایش لیست قالب‌های واتساپ"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    is_active = request.GET.get('is_active', '')
    
    # فیلتر کردن داده‌ها
    templates = WhatsappTemplate.objects.all()
    
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
    total_count = WhatsappTemplate.objects.count()
    default_count = WhatsappTemplate.objects.filter(is_active=True).count()
    
    context = {
        'templates': templates,
        'status_filter': status,
        'search': search,
        'is_active': is_active,
        'total_count': total_count,
        'default_count': default_count,
        'status_choices': WhatsappTemplate.STATUS_CHOICES,
        'placeholders': WhatsappTemplate.get_available_placeholders()
    }
    
    return render(request, 'whatsapp_api/template_list.html', context)

@role_required('admin')
@login_required
def template_create(request):
    """ایجاد قالب واتساپ جدید"""
    # دریافت مقدار پیش‌فرض برای وضعیت انتخاب شده
    preselected_status = request.GET.get('status', '')
    default_content = ''
    
    if request.method == 'POST':
        name = request.POST.get('name')
        status = request.POST.get('status')
        template_type = request.POST.get('template_type')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not status or not content or not template_type:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید.')
            return redirect('whatsapp_api:template_create')
        
        try:
            template = WhatsappTemplate.objects.create(
                name=name,
                status=status,
                template_type=template_type,
                content=content,
                description=description,
                is_active=is_active
            )
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را برای این وضعیت غیرفعال می‌کنیم
            if is_active:
                WhatsappTemplate.objects.filter(status=status, is_active=True).exclude(id=template.id).update(is_active=False)
                
            messages.success(request, f'قالب "{template.name}" با موفقیت ایجاد شد.')
            return redirect('whatsapp_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد قالب: {str(e)}')
            
    context = {
        'status_choices': WhatsappTemplate.STATUS_CHOICES,
        'template_types': WhatsappTemplate.TEMPLATE_TYPES,
        'placeholders': WhatsappTemplate.get_available_placeholders(),
        'preselected_status': preselected_status,
        'default_content': default_content
    }
    
    return render(request, 'whatsapp_api/template_create.html', context)

@role_required('admin')
@login_required
def template_edit(request, template_id):
    """ویرایش قالب واتساپ"""
    template = get_object_or_404(WhatsappTemplate, id=template_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        status = request.POST.get('status')
        template_type = request.POST.get('template_type')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not status or not content or not template_type:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید.')
            return redirect('whatsapp_api:template_edit', template_id=template_id)
        
        try:
            # بررسی تغییر وضعیت
            status_changed = template.status != status
            
            # ذخیره مقادیر جدید
            template.name = name
            template.status = status
            template.template_type = template_type
            template.content = content
            template.description = description
            template.is_active = is_active
            template.save()
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را برای این وضعیت غیرفعال می‌کنیم
            if is_active:
                WhatsappTemplate.objects.filter(status=status, is_active=True).exclude(id=template.id).update(is_active=False)
            
            messages.success(request, f'قالب "{template.name}" با موفقیت بروزرسانی شد.')
            return redirect('whatsapp_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در بروزرسانی قالب: {str(e)}')
    
    context = {
        'template': template,
        'status_choices': WhatsappTemplate.STATUS_CHOICES,
        'template_types': WhatsappTemplate.TEMPLATE_TYPES,
        'placeholders': WhatsappTemplate.get_available_placeholders(),
    }
    
    return render(request, 'whatsapp_api/template_edit.html', context)

@role_required('admin')
@login_required
def template_detail(request, template_id):
    """مشاهده جزئیات قالب واتساپ"""
    template = get_object_or_404(WhatsappTemplate, id=template_id)
    
    context = {
        'template': template,
        'placeholders': WhatsappTemplate.get_available_placeholders()
    }
    
    return render(request, 'whatsapp_api/template_detail.html', context)

@role_required('admin')
@login_required
@require_POST
def template_delete(request, template_id):
    """حذف قالب واتساپ"""
    template = get_object_or_404(WhatsappTemplate, id=template_id)
    
    # اگر قالب پیش‌فرض است و قالب دیگری از این نوع وجود ندارد، اجازه حذف نمی‌دهیم
    if template.is_active and WhatsappTemplate.objects.filter(status=template.status).count() == 1:
        messages.error(request, 'نمی‌توانید تنها قالب پیش‌فرض یک وضعیت را حذف کنید.')
        return redirect('whatsapp_api:template_list')
    
    try:
        template_name = template.name
        template.delete()
        messages.success(request, f'قالب "{template_name}" با موفقیت حذف شد.')
    except Exception as e:
        messages.error(request, f'خطا در حذف قالب: {str(e)}')
    
    return redirect('whatsapp_api:template_list')

@role_required('admin')
@login_required
@require_POST
def set_template_default(request, template_id):
    """تنظیم قالب به عنوان پیش‌فرض"""
    template = get_object_or_404(WhatsappTemplate, id=template_id)
    
    try:
        # قالب‌های پیش‌فرض دیگر از همین وضعیت را غیرفعال می‌کنیم
        WhatsappTemplate.objects.filter(status=template.status, is_active=True).update(is_active=False)
        
        # این قالب را پیش‌فرض می‌کنیم
        template.is_active = True
        template.save()
        
        messages.success(request, f'قالب "{template.name}" به عنوان پیش‌فرض برای وضعیت "{template.get_status_display()}" تنظیم شد.')
    except Exception as e:
        messages.error(request, f'خطا در تنظیم قالب پیش‌فرض: {str(e)}')
    
    return redirect('whatsapp_api:template_list')

@role_required('admin')
@login_required
def template_preview(request, template_id):
    """پیش‌نمایش قالب واتساپ با داده‌های آزمایشی"""
    template = get_object_or_404(WhatsappTemplate, id=template_id)
    
    # داده‌های آزمایشی برای پیش‌نمایش - با فرمت ساختاری
    sample_data = {
        'customer_name': 'مشتری نمونه',
        'purchase_number': '1234567',
        'invoice_id': '12345',
        'order_weight': '25000',
        'customer_price': '150000',
        'amount_paid': '3750000000',
        'barnameh': 'B-987654',
        'barnameh_date': '1402/06/15',
        'driver_name': 'راننده نمونه',
        'driver_phone': '09123456789',
        'extelaf_type': 'کسری',
        'extelaf_weight': '500',
        'extelaf_amount': '75000000',
        'cottage': '12345678',
        'product_type': 'ذرت',
        'product_country': 'برزیل',
        'sales_agent_name': 'کارشناس فروش نمونه',
        'sales_agent_phone': '09123456789',
        'dakheli_number': '3',
        'shenase_takhsis': 'ABC123456789',
    }
    
    # پردازش قالب با داده‌های نمونه
    import re
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
    
    return render(request, 'whatsapp_api/template_preview.html', context)

@role_required('admin')
@login_required
def template_test(request, template_id):
    """ارسال پیام واتساپ آزمایشی با استفاده از قالب"""
    template = get_object_or_404(WhatsappTemplate, id=template_id)
    
    if request.method == 'POST':
        recipient_number = request.POST.get('recipient_number')
        
        if not recipient_number:
            messages.error(request, 'لطفاً شماره تلفن را وارد کنید.')
            return redirect('whatsapp_api:template_test', template_id=template_id)
        
        try:
            # داده‌های آزمایشی برای پردازش قالب
            sample_data = {
                'customer_name': 'مشتری نمونه',
                'purchase_number': '1234567',
                'invoice_id': '12345',
                'order_weight': '25000',
                'customer_price': '150000',
                'amount_paid': '3750000000',
                'barnameh': 'B-987654',
                'barnameh_date': '1402/06/15',
                'driver_name': 'راننده نمونه',
                'driver_phone': '09123456789',
                'extelaf_type': 'کسری',
                'extelaf_weight': '500',
                'extelaf_amount': '75000000',
                'cottage': '12345678',
                'product_type' : 'ذرت',
                'product_country': 'برزیل',
                'sales_agent_name': 'کارشناس فروش نمونه',
                'sales_agent_phone': '09123456789',
                'dakheli_number': '3',
                'shenase_takhsis': 'ABC123456789',
            }
            
            # پردازش قالب
            import re
            message_text = template.content
            for key, value in sample_data.items():
                # ایجاد الگوی جستجو با در نظر گرفتن فضای خالی احتمالی
                pattern = r'{{\s*' + re.escape(key) + r'\s*}}'
                message_text = re.sub(pattern, value, message_text)
            
            # ایجاد آیتم در صف ارسال
            queue_item = WhatsappQueue.objects.create(
                recipient_number=recipient_number,
                template_type=template.template_type,
                message=message_text,
                status='pending',
                notification_type='custom'
            )
            
            # ارسال واقعی
            success = send_whatsapp_message(recipient_number, template.template_type, sample_data)
            
            if success:
                queue_item.status = 'sent'
                queue_item.sent_at = timezone.now()
                queue_item.save()
                WhatsappLog.objects.create(
                    recipient_number=recipient_number,
                    template_type=template.template_type,
                    message=message_text,
                    status='sent',
                    sent_at=queue_item.sent_at
                )
                messages.success(request, f'پیام آزمایشی به شماره {recipient_number} ارسال شد.')
            else:
                queue_item.status = 'failed'
                queue_item.save()
                messages.error(request, 'ارسال پیام آزمایشی ناموفق بود.')
                
            return redirect('whatsapp_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در ارسال پیام آزمایشی: {str(e)}')
    
    context = {
        'template': template
    }
    
    return render(request, 'whatsapp_api/template_test.html', context)

@role_required('admin', 'support_agent')
@login_required
def get_templates_for_status(request):
    """Returns all templates for a specific status as JSON"""
    status = request.GET.get('status', '')
    
    if not status:
        return JsonResponse({'error': 'Status parameter is required'}, status=400)
    
    # Get all templates for the specified status
    templates = WhatsappTemplate.objects.filter(status=status).order_by('-is_active', '-updated_at')
    
    # Convert templates to a list of dicts for JSON serialization
    templates_list = []
    for template in templates:
        templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'template_type': template.template_type,
            'template_type_display': template.get_template_type_display(),
            'description': template.description or '',
            'is_active': template.is_active,
            'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return JsonResponse({
        'status': status,
        'status_display': dict(WhatsappTemplate.STATUS_CHOICES).get(status, status),
        'templates': templates_list,
        'count': len(templates_list)
    })