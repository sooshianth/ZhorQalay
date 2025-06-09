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
from .queue_utils import queue_whatsapp_message, process_whatsapp_queue, check_missing_whatsapp_templates, create_default_whatsapp_templates, get_default_whatsapp_templates
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

@role_required('admin', 'support_agent')
@login_required
def send_whatsapp(request):
    notification_types = dict(WhatsappQueue.NOTIFICATION_TYPES)
    
    # Get purchase templates from WhatsappTemplate model
    templates_dict = {}
    
    # Get all purchase templates for each status from the database
    status_templates = {}
    purchase_templates = WhatsappTemplate.objects.filter(template_type='purchase')
    
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
    marketing_templates = WhatsappTemplate.objects.filter(template_type='marketing').order_by('-is_active', '-updated_at')
    marketing_templates_list = []
    for template in marketing_templates:
        marketing_templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_default': template.is_active,
            'is_active': template.is_active
        })
    marketing_templates_json = json.dumps(marketing_templates_list)
    
    # Get product templates (all templates, not just active ones)
    product_templates = WhatsappTemplate.objects.filter(template_type='product_notification').order_by('-is_active', '-updated_at')
    product_templates_list = []
    for template in product_templates:
        product_templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'description': template.description or '',
            'is_default': template.is_active,
            'is_active': template.is_active
        })
    product_templates_json = json.dumps(product_templates_list)
    
    # Create a dictionary of status display names
    purchase_statuses = {}
    for status_code, status_name in Purchase.STATUS_CHOICES:
        purchase_statuses[status_code] = status_name
    purchase_statuses_json = json.dumps(purchase_statuses)
    
    # Get all active cargo products for product selection modal
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
            whatsapp_type = request.POST.get('whatsapp_type')
            message = request.POST.get('message')
            notification_type = request.POST.get('notification_type', 'custom')
            scheduled_for_str = request.POST.get('scheduled_for')
            
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
                            
                    # ارسال واتساپ به مشتری
                    success_count = 0
                    try:
                        phone = customer.get_primary_phone()
                        if phone:
                            # استاندارد کردن شماره برای واتساپ
                            if phone.startswith('0'):
                                phone = '+98' + phone[1:]
                            elif not phone.startswith('+98'):
                                phone = '+98' + phone
                            
                            queue_whatsapp_message(
                                recipient_number=phone,
                                message=message,
                                notification_type=notification_type,
                                scheduled_for=scheduled_for,
                                purchase=purchase,
                                template_type='purchase'
                            )
                            success_count += 1
                    except Exception as e:
                        logger.error(f"خطا در ایجاد پیام واتساپ برای شماره {phone}: {str(e)}")
                        messages.error(request, f'خطا در ایجاد پیام واتساپ برای شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'پیام واتساپ با موفقیت به صف ارسال اضافه شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, 'هیچ پیام واتساپی با موفقیت به صف ارسال اضافه نشد.')
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
                    
                    # ارسال واتساپ به مشتری
                    success_count = 0
                    try:
                        phone = customer.get_primary_phone()
                        if phone:
                            # استاندارد کردن شماره برای واتساپ
                            if phone.startswith('0'):
                                phone = '+98' + phone[1:]
                            elif not phone.startswith('+98'):
                                phone = '+98' + phone
                            
                            queue_whatsapp_message(
                                recipient_number=phone,
                                message=message,
                                notification_type='SMS_SENT',  # نوع اطلاع‌رسانی پیش‌فرض برای کوتاژ
                                scheduled_for=scheduled_for,
                                template_type='product_notification'
                            )
                            success_count += 1
                    except Exception as e:
                        logger.error(f"خطا در ایجاد پیام واتساپ برای شماره {phone}: {str(e)}")
                        messages.error(request, f'خطا در ایجاد پیام واتساپ برای شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'پیام واتساپ اطلاع‌رسانی کوتاژ با موفقیت به صف ارسال اضافه شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, 'هیچ پیام واتساپی با موفقیت به صف ارسال اضافه نشد.')
                elif message_type == 'marketing':
                    # ارسال پیام تبلیغاتی به مشتری انتخاب شده
                    success_count = 0
                    try:
                        phone = customer.get_primary_phone()
                        if phone:
                            # استاندارد کردن شماره برای واتساپ
                            if phone.startswith('0'):
                                phone = '+98' + phone[1:]
                            elif not phone.startswith('+98'):
                                phone = '+98' + phone
                            
                            queue_whatsapp_message(
                                recipient_number=phone,
                                message=message,
                                notification_type='MARKETING',  # نوع اطلاع‌رسانی پیش‌فرض برای تبلیغات
                                scheduled_for=scheduled_for,
                                template_type='marketing'
                            )
                            success_count += 1
                    except Exception as e:
                        logger.error(f"خطا در ایجاد پیام واتساپ برای شماره {phone}: {str(e)}")
                        messages.error(request, f'خطا در ایجاد پیام واتساپ برای شماره {phone}: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت به صف ارسال اضافه شد.')
                        return redirect('whatsapp_api:whatsapp-dashboard')
                    else:
                        messages.error(request, 'هیچ پیام واتساپی با موفقیت به صف ارسال اضافه نشد.')
            elif whatsapp_type == 'marketing':
                # ارسال پیام تبلیغاتی به شماره دلخواه
                recipient_number = request.POST.get('recipient_number')
                
                if not recipient_number:
                    messages.error(request, 'لطفاً شماره گیرنده را وارد کنید.')
                    return redirect('whatsapp_api:send-whatsapp')
                
                # اعتبارسنجی شماره تلفن
                phone_regex = r'^(0|0098|\+98)?9\d{9}$'
                if not re.match(phone_regex, recipient_number):
                    messages.error(request, 'فرمت شماره تلفن نامعتبر است.')
                    return redirect('whatsapp_api:send-whatsapp')
                
                # استاندارد کردن فرمت شماره تلفن برای واتساپ
                if recipient_number.startswith('+98'):
                    pass  # already correct
                elif recipient_number.startswith('0098'):
                    recipient_number = '+98' + recipient_number[4:]
                elif recipient_number.startswith('0'):
                    recipient_number = '+98' + recipient_number[1:]
                else:
                    recipient_number = '+98' + recipient_number
                
                try:
                    queue_whatsapp_message(
                        recipient_number=recipient_number,
                        message=message,
                        notification_type='MARKETING',  # نوع اطلاع‌رسانی پیش‌فرض برای تبلیغات
                        scheduled_for=scheduled_for,
                        template_type='marketing'
                    )
                    messages.success(request, f'پیام واتساپ تبلیغاتی با موفقیت به صف ارسال برای شماره {recipient_number} اضافه شد.')
                    return redirect('whatsapp_api:whatsapp-dashboard')
                except Exception as e:
                    logger.error(f"خطا در ایجاد پیام واتساپ تبلیغاتی برای شماره {recipient_number}: {str(e)}")
                    messages.error(request, f'خطا در ایجاد پیام واتساپ تبلیغاتی: {str(e)}')
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ایجاد پیام واتساپ: {str(e)}")
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
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    
    # فیلتر کردن داده‌ها
    queue_items = WhatsappQueue.objects.all()
    
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
    
    # تعداد پیام‌ها با وضعیت‌های مختلف
    pending_count = WhatsappQueue.objects.filter(status='pending').count()
    sent_count = WhatsappQueue.objects.filter(status='sent').count()
    failed_count = WhatsappQueue.objects.filter(status='failed').count()
    suspended_count = WhatsappQueue.objects.filter(status='suspended').count()
    
    context = {
        'queue_items': queue_items,
        'status': status,
        'notification_type': notification_type,
        'search': search,
        'pending_count': pending_count,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'suspended_count': suspended_count,
        'notification_types': WhatsappQueue.NOTIFICATION_TYPES,
    }
    
    return render(request, 'whatsapp_api/whatsapp_queue.html', context)

@role_required('admin')
@login_required
def template_list(request):
    """نمایش لیست قالب‌های واتساپ"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    template_type = request.GET.get('template_type', '')
    search = request.GET.get('search', '')
    is_active = request.GET.get('is_active', '')
    
    # فیلتر کردن داده‌ها
    templates = WhatsappTemplate.objects.all()
    
    if status:
        templates = templates.filter(status=status)
    
    if template_type:
        templates = templates.filter(template_type=template_type)
    
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
    templates = templates.order_by('template_type', '-is_active', '-updated_at')
    
    # صفحه‌بندی
    paginator = Paginator(templates, 10)  # 10 آیتم در هر صفحه
    page_number = request.GET.get('page', 1)
    templates = paginator.get_page(page_number)
    
    # آمار
    total_count = WhatsappTemplate.objects.count()
    default_count = WhatsappTemplate.objects.filter(is_active=True).count()
    purchase_count = WhatsappTemplate.objects.filter(template_type='purchase').count()
    product_count = WhatsappTemplate.objects.filter(template_type='product_notification').count()
    marketing_count = WhatsappTemplate.objects.filter(template_type='marketing').count()
    
    context = {
        'templates': templates,
        'status_filter': status,
        'template_type_filter': template_type,
        'search': search,
        'is_active': is_active,
        'total_count': total_count,
        'default_count': default_count,
        'purchase_count': purchase_count,
        'product_count': product_count,
        'marketing_count': marketing_count,
        'status_choices': WhatsappTemplate.STATUS_CHOICES,
        'template_type_choices': WhatsappTemplate.TEMPLATE_TYPES,
        'template_types': WhatsappTemplate.TEMPLATE_TYPES,  # برای سازگاری
        'placeholders': WhatsappTemplate.get_available_placeholders()
    }
    
    return render(request, 'whatsapp_api/template_list.html', context)

@role_required('admin')
@login_required
def template_create(request):
    """ایجاد قالب واتساپ جدید"""
    # دریافت مقدار پیش‌فرض برای وضعیت انتخاب شده
    preselected_status = request.GET.get('status', '')
    preselected_type = request.GET.get('template_type', 'purchase')
    default_content = ''
    
    if request.method == 'POST':
        name = request.POST.get('name')
        status = request.POST.get('status')
        template_type = request.POST.get('template_type')
        content = request.POST.get('content')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        # بررسی فیلدهای ضروری
        if not name or not content or not template_type:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید.')
            return redirect('whatsapp_api:template_create')
        
        # برای قالب‌های خرید، وضعیت ضروری است
        if template_type == 'purchase' and not status:
            messages.error(request, 'برای قالب‌های مربوط به خرید، انتخاب وضعیت ضروری است.')
            return redirect('whatsapp_api:template_create')
        
        try:
            template = WhatsappTemplate.objects.create(
                name=name,
                status=status if template_type == 'purchase' else None,
                template_type=template_type,
                content=content,
                description=description,
                is_active=is_active
            )
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را غیرفعال می‌کنیم
            if is_active:
                if template_type == 'purchase' and status:
                    # برای قالب‌های خرید، بر اساس وضعیت
                    WhatsappTemplate.objects.filter(
                        status=status, 
                        template_type='purchase', 
                        is_active=True
                    ).exclude(id=template.id).update(is_active=False)
                else:
                    # برای قالب‌های دیگر، بر اساس نوع
                    WhatsappTemplate.objects.filter(
                        template_type=template_type, 
                        is_active=True
                    ).exclude(id=template.id).update(is_active=False)
                
            messages.success(request, f'قالب "{template.name}" با موفقیت ایجاد شد.')
            return redirect('whatsapp_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد قالب: {str(e)}')
    
    # قالب‌های پیش‌فرض برای هر نوع و وضعیت
    default_templates = {
        'purchase': {
            'INITIATED': 'مشتری گرامی {{customer_name}}\nخرید شما به شماره {{purchase_number}} ثبت گردید.✅\nلطفاً هر چه سریع‌تر نسبت به ثبت آدرس خود اقدام فرمایید.\nشرکت تامین نهاده سیمرغ',
            'PAYMENT_VERIFIED': 'مشتری گرامی {{customer_name}}\nپرداخت خرید {{purchase_number}} تایید شد.✅\nبزودی آدرس شما برای بارگیری ارسال خواهد شد.\nشرکت تامین نهاده سیمرغ',
            'BARNAMEH_ISSUED': '{{customer_name}} عزیز؛\nبارنامه خرید {{purchase_number}}:\nشماره بارنامه: {{barnameh}}\nتاریخ: {{barnameh_date}}\nراننده: {{driver_name}} - {{driver_phone}}\nشرکت تامین نهاده سیمرغ',
            'PURCHASE_CLOSED': 'مشتری گرامی\nخرید شما {{purchase_number}} با موفقیت تکمیل شد.✅\nاز اعتماد شما سپاسگزاریم 💚\nکارشناس فروش: {{sales_agent_name}}\nشرکت تامین نهاده سیمرغ'
        },
        'product_notification': 'مشتری گرامی\nمحصولات جدید وارداتی به انبار ما رسیده است:\n{{product_type}} {{product_country}}\nکوتاژ: {{cottage}}\nوزن: {{order_weight}} کیلوگرم\nبرای اطلاع از قیمت با ما تماس بگیرید.\nشرکت تامین نهاده سیمرغ',
        'marketing': 'مشتری گرامی\nشرکت تامین نهاده سیمرغ همیشه در کنار شماست.\nبرای مشاوره رایگان در زمینه واردات با ما تماس بگیرید.\n📞 ۰۲۱-۶۶۵۶۲۲۱۶\nشرکت تامین نهاده سیمرغ'
    }
    
    import json
    
    context = {
        'status_choices': WhatsappTemplate.STATUS_CHOICES,
        'template_type_choices': WhatsappTemplate.TEMPLATE_TYPES,
        'template_types': WhatsappTemplate.TEMPLATE_TYPES,  # برای سازگاری
        'placeholders': WhatsappTemplate.get_available_placeholders(),
        'preselected_status': preselected_status,
        'preselected_type': preselected_type,
        'default_content': default_content,
        'default_templates': json.dumps(default_templates)
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
        
        # بررسی فیلدهای ضروری
        if not name or not content or not template_type:
            messages.error(request, 'لطفاً تمام فیلدهای ضروری را پر کنید.')
            return redirect('whatsapp_api:template_edit', template_id=template_id)
        
        # برای قالب‌های خرید، وضعیت ضروری است
        if template_type == 'purchase' and not status:
            messages.error(request, 'برای قالب‌های مربوط به خرید، انتخاب وضعیت ضروری است.')
            return redirect('whatsapp_api:template_edit', template_id=template_id)
        
        try:
            # ذخیره مقادیر جدید
            template.name = name
            template.status = status if template_type == 'purchase' else None
            template.template_type = template_type
            template.content = content
            template.description = description
            template.is_active = is_active
            template.save()
            
            # اگر این قالب به عنوان پیش‌فرض تنظیم شده، قالب‌های پیش‌فرض دیگر را غیرفعال می‌کنیم
            if is_active:
                if template_type == 'purchase' and status:
                    # برای قالب‌های خرید، بر اساس وضعیت
                    WhatsappTemplate.objects.filter(
                        status=status, 
                        template_type='purchase', 
                        is_active=True
                    ).exclude(id=template.id).update(is_active=False)
                else:
                    # برای قالب‌های دیگر، بر اساس نوع
                    WhatsappTemplate.objects.filter(
                        template_type=template_type, 
                        is_active=True
                    ).exclude(id=template.id).update(is_active=False)
            
            messages.success(request, f'قالب "{template.name}" با موفقیت بروزرسانی شد.')
            return redirect('whatsapp_api:template_list')
        except Exception as e:
            messages.error(request, f'خطا در بروزرسانی قالب: {str(e)}')
    
    context = {
        'template': template,
        'status_choices': WhatsappTemplate.STATUS_CHOICES,
        'template_type_choices': WhatsappTemplate.TEMPLATE_TYPES,
        'template_types': WhatsappTemplate.TEMPLATE_TYPES,  # برای سازگاری
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
        # قالب‌های پیش‌فرض دیگر را غیرفعال می‌کنیم
        if template.template_type == 'purchase' and template.status:
            # برای قالب‌های خرید، بر اساس وضعیت
            WhatsappTemplate.objects.filter(
                status=template.status, 
                template_type='purchase', 
                is_active=True
            ).update(is_active=False)
            message = f'قالب "{template.name}" به عنوان پیش‌فرض برای وضعیت "{template.get_status_display()}" تنظیم شد.'
        else:
            # برای قالب‌های دیگر، بر اساس نوع
            WhatsappTemplate.objects.filter(
                template_type=template.template_type, 
                is_active=True
            ).update(is_active=False)
            message = f'قالب "{template.name}" به عنوان پیش‌فرض برای "{template.get_template_type_display()}" تنظیم شد.'
        
        # این قالب را پیش‌فرض می‌کنیم
        template.is_active = True
        template.save()
        
        messages.success(request, message)
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

# Views جدید برای مدیریت صف واتساپ

@role_required('admin')
@login_required
def whatsapp_detail(request, whatsapp_id):
    """نمایش جزئیات پیام واتساپ"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    logs = WhatsappLog.objects.filter(recipient_number=whatsapp.recipient_number).order_by('-sent_at')
    
    context = {
        'whatsapp': whatsapp,
        'logs': logs
    }
    return render(request, 'whatsapp_api/whatsapp_detail.html', context)

@role_required('admin')
@login_required
def edit_whatsapp(request, whatsapp_id):
    """ویرایش پیام واتساپ"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    
    # فقط پیام‌های در انتظار یا معلق قابل ویرایش هستند
    if whatsapp.status not in ['pending', 'suspended']:
        messages.error(request, 'فقط پیام‌های در انتظار یا معلق قابل ویرایش هستند.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    if request.method == 'POST':
        recipient_number = request.POST.get('recipient_number')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type')
        scheduled_for = request.POST.get('scheduled_for')
        purchase_id = request.POST.get('purchase_id')
        
        # اعتبارسنجی داده‌ها
        if not recipient_number or not message:
            messages.error(request, 'لطفاً تمامی فیلدهای ضروری را پر کنید.')
            return redirect('whatsapp_api:edit_whatsapp', whatsapp_id=whatsapp.id)
        
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
        
        # به‌روزرسانی پیام واتساپ
        whatsapp.recipient_number = recipient_number
        whatsapp.message = message
        whatsapp.notification_type = notification_type
        whatsapp.scheduled_for = scheduled_for
        whatsapp.purchase_id = purchase_id
        whatsapp.save()
        
        messages.success(request, 'پیام واتساپ با موفقیت به‌روزرسانی شد.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    # انواع اطلاع‌رسانی
    notification_types = WhatsappQueue.NOTIFICATION_TYPES
    
    context = {
        'whatsapp': whatsapp,
        'notification_types': notification_types,
        'scheduled_for': whatsapp.scheduled_for.strftime('%Y-%m-%dT%H:%M') if whatsapp.scheduled_for else None,
    }
    
    return render(request, 'whatsapp_api/edit_whatsapp.html', context)

@role_required('admin')
@login_required
@require_POST
def delete_whatsapp(request, whatsapp_id):
    """حذف پیام واتساپ"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    
    # فقط پیام‌های در انتظار یا معلق قابل حذف هستند
    if whatsapp.status not in ['pending', 'suspended']:
        messages.error(request, 'فقط پیام‌های در انتظار یا معلق قابل حذف هستند.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    whatsapp.delete()
    messages.success(request, 'پیام واتساپ با موفقیت حذف شد.')
    return redirect('whatsapp_api:whatsapp-queue')

@role_required('admin')
@login_required
@require_POST
def suspend_whatsapp(request, whatsapp_id):
    """تعلیق پیام واتساپ"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    
    # فقط پیام‌های در انتظار قابل تعلیق هستند
    if whatsapp.status != 'pending':
        messages.error(request, 'فقط پیام‌های در انتظار قابل تعلیق هستند.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    whatsapp.status = 'suspended'
    whatsapp.is_suspended = True
    whatsapp.save()
    
    messages.success(request, 'پیام واتساپ با موفقیت معلق شد.')
    return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)

@role_required('admin')
@login_required
@require_POST
def resume_whatsapp(request, whatsapp_id):
    """از سرگیری پیام واتساپ معلق"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    
    # فقط پیام‌های معلق قابل از سرگیری هستند
    if whatsapp.status != 'suspended':
        messages.error(request, 'فقط پیام‌های معلق قابل از سرگیری هستند.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    whatsapp.status = 'pending'
    whatsapp.is_suspended = False
    whatsapp.save()
    
    messages.success(request, 'پیام واتساپ با موفقیت از سرگرفته شد.')
    return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)

@role_required('admin')
@login_required
@require_POST
def send_whatsapp_now(request, whatsapp_id):
    """ارسال فوری پیام واتساپ"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    
    # فقط پیام‌های در انتظار قابل ارسال فوری هستند
    if whatsapp.status != 'pending':
        messages.error(request, 'فقط پیام‌های در انتظار قابل ارسال فوری هستند.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    # اگر پیام مرتبط با خرید است و مشتری دارد، به همه شماره‌های مشتری ارسال شود
    if whatsapp.purchase and hasattr(whatsapp.purchase, 'customer') and whatsapp.purchase.customer:
        customer = whatsapp.purchase.customer
        phone_numbers = [customer.get_primary_phone()]
        phone_numbers = [phone for phone in phone_numbers if phone]  # حذف شماره‌های خالی
        
        if not phone_numbers:
            messages.error(request, f'هیچ شماره تلفنی برای مشتری {customer.name} یافت نشد.')
            return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
        
        success_count = 0
        for phone in phone_numbers:
            success = send_whatsapp_message(phone, whatsapp.template_type, {
                'customer_name': customer.name,
                'purchase_number': whatsapp.purchase.purchase_number,
                'message': whatsapp.message
            })
            
            if success:
                # ثبت در لاگ
                WhatsappLog.objects.create(
                    recipient_number=phone,
                    message=whatsapp.message,
                    template_type=whatsapp.template_type,
                    status='sent',
                    purchase=whatsapp.purchase
                )
                success_count += 1
        
        if success_count > 0:
            # به‌روزرسانی وضعیت پیام اصلی
            whatsapp.status = 'sent'
            whatsapp.sent_at = timezone.now()
            whatsapp.save()
            
            messages.success(request, f'پیام واتساپ با موفقیت به {success_count} شماره ارسال شد.')
        else:
            messages.error(request, 'ارسال پیام واتساپ ناموفق بود. لطفا دوباره تلاش کنید.')
    else:
        # ارسال به یک شماره تکی
        success = send_whatsapp_message(whatsapp.recipient_number, whatsapp.template_type, {})
            
        # به‌روزرسانی وضعیت پیام
        if success:
            whatsapp.status = 'sent'
            whatsapp.sent_at = timezone.now()
            whatsapp.save()
            
            # ثبت در لاگ
            WhatsappLog.objects.create(
                recipient_number=whatsapp.recipient_number,
                message=whatsapp.message,
                template_type=whatsapp.template_type,
                status='sent',
                purchase=whatsapp.purchase
            )
            
            messages.success(request, 'پیام واتساپ با موفقیت ارسال شد.')
        else:
            messages.error(request, 'ارسال پیام واتساپ ناموفق بود. لطفا دوباره تلاش کنید.')
            
    return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)

@role_required('admin')
@login_required
@require_POST
def retry_whatsapp(request, whatsapp_id):
    """تلاش مجدد برای ارسال پیام واتساپ ناموفق"""
    whatsapp = get_object_or_404(WhatsappQueue, id=whatsapp_id)
    
    # فقط پیام‌های ناموفق قابل ارسال مجدد هستند
    if whatsapp.status != 'failed':
        messages.error(request, 'فقط پیام‌های ناموفق قابل ارسال مجدد هستند.')
        return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)
    
    whatsapp.status = 'pending'
    whatsapp.retry_count += 1
    whatsapp.save()
    
    messages.success(request, 'پیام واتساپ برای ارسال مجدد در صف قرار گرفت.')
    return redirect('whatsapp_api:whatsapp_detail', whatsapp_id=whatsapp.id)

@role_required('admin')
@login_required
@require_POST
def process_whatsapp_queue_manually(request):
    """
    اجرای دستی پردازش صف پیام‌های واتساپ
    برای مواقعی که سیستم خودکار (سلری) در دسترس نیست
    """
    try:
        # اجرای پردازش صف پیام‌های واتساپ
        results = process_whatsapp_queue()
        
        # تعداد پیام‌های ارسال شده
        sent_count = sum(1 for r in results if r.get("status") == "sent")
        
        # تعداد پیام‌های ناموفق
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        
        if not results:
            messages.info(request, "هیچ پیام واتساپی در صف ارسال یافت نشد.")
        else:
            messages.success(
                request, 
                f"پردازش صف با موفقیت انجام شد. {sent_count} پیام ارسال شد و {failed_count} پیام ناموفق بود."
            )
            
        # ثبت لاگ
        logger.info(f"پردازش دستی صف واتساپ توسط کاربر {request.user}: {len(results)} پیام")
        
    except Exception as e:
        messages.error(request, f"خطا در پردازش صف واتساپ: {str(e)}")
        logger.error(f"خطا در پردازش دستی صف واتساپ: {str(e)}")
    
    # بازگشت به صفحه قبلی
    return redirect('whatsapp_api:whatsapp-queue')

# Template Management Views

@role_required('admin')
@login_required
def template_check(request):
    """نمایش وضعیت قالب‌های واتساپ و ایجاد قالب‌های پیش‌فرض"""
    # Check for missing templates
    missing_templates = check_missing_whatsapp_templates()
    
    # If form submitted, create missing templates
    if request.method == 'POST':
        replace_existing = request.POST.get('replace_existing', 'off') == 'on'
        created, updated, skipped = create_default_whatsapp_templates(replace_existing)
        
        if created > 0:
            messages.success(request, f"{created} قالب جدید با موفقیت ایجاد شد.")
        if updated > 0:
            messages.success(request, f"{updated} قالب موجود به‌روزرسانی شد.")
        if skipped > 0:
            messages.info(request, f"{skipped} قالب موجود بدون تغییر باقی ماند.")
            
        # Redirect to avoid resubmission
        return redirect('whatsapp_api:template_check')
    
    context = {
        'missing_templates': missing_templates,
        'missing_count': len(missing_templates),
        'all_statuses_count': len([status[0] for status in Purchase.STATUS_CHOICES]),
    }
    
    return render(request, 'whatsapp_api/template_check.html', context)

@role_required('admin', 'support_agent')
@login_required
def get_templates_for_status(request):
    """Returns all templates for a specific status as JSON"""
    status = request.GET.get('status', '')
    template_type = request.GET.get('template_type', 'purchase')  # Default to purchase templates
    
    if not status and template_type == 'purchase':
        return JsonResponse({'error': 'Status parameter is required for purchase templates'}, status=400)
    
    # Get templates based on type
    if template_type == 'purchase':
        templates = WhatsappTemplate.objects.filter(
            status=status, 
            template_type='purchase'
        ).order_by('-is_active', '-updated_at')
    else:
        # For product_notification and marketing templates
        templates = WhatsappTemplate.objects.filter(
            template_type=template_type
        ).order_by('-is_active', '-updated_at')
    
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
        'template_type': template_type,
        'status_display': dict(Purchase.STATUS_CHOICES).get(status, status) if status else '',
        'templates': templates_list,
        'count': len(templates_list)
    })

@role_required('admin', 'support_agent')
@login_required
def get_templates_by_type(request):
    """Returns all templates for a specific type as JSON"""
    template_type = request.GET.get('template_type', 'purchase')
    
    # Get templates based on type
    templates = WhatsappTemplate.objects.filter(
        template_type=template_type
    ).order_by('-is_active', '-updated_at')
    
    # Convert templates to a list of dicts for JSON serialization
    templates_list = []
    for template in templates:
        templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'template_type': template.template_type,
            'template_type_display': template.get_template_type_display(),
            'status': template.status,
            'status_display': dict(Purchase.STATUS_CHOICES).get(template.status, template.status) if template.status else '',
            'description': template.description or '',
            'is_active': template.is_active,
            'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        })
    
    return JsonResponse({
        'template_type': template_type,
        'template_type_display': dict(WhatsappTemplate.TEMPLATE_TYPES).get(template_type, template_type),
        'templates': templates_list,
        'count': len(templates_list)
    })

@role_required('admin', 'support_agent')
@login_required  
def get_customer_purchases(request):
    """Returns customer purchases with their status as JSON"""
    customer_id = request.GET.get('customer_id', '')
    
    if not customer_id:
        return JsonResponse({'error': 'Customer ID parameter is required'}, status=400)
    
    try:
        customer = Customer.objects.get(pk=customer_id)
        purchases = Purchase.objects.filter(customer=customer).order_by('-created_at')[:20]
        
        purchases_list = []
        for purchase in purchases:
            purchases_list.append({
                'id': purchase.id,
                'purchase_number': purchase.purchase_number,
                'invoice_id': purchase.invoice_id or '',
                'state': purchase.state,
                'state_display': purchase.get_state_display(),
                'order_weight': str(purchase.order_weight or ''),
                'customer_price': str(purchase.customer_price or ''),
                'amount_paid': str(purchase.amount_paid or ''),
                'created_at': purchase.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'barnameh': purchase.barnameh or '',
                'barnameh_date': str(purchase.barnameh_date or ''),
            })
        
        return JsonResponse({
            'customer_id': customer_id,
            'customer_name': customer.name,
            'purchases': purchases_list,
            'count': len(purchases_list)
        })
        
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)