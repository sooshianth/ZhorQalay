from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import WhatsappNumber, WhatsappLog, WhatsappTemplate, WhatsappQueue
from .utils import send_whatsapp_message
from core._models import Customer
from django.db import models
from core.decorators.decorators import role_required

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
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        customer_id = request.POST.get('customer_id')
        template_type = request.POST.get('template_type')

        try:
            template = WhatsappTemplate.objects.get(template_type=template_type, is_active=True)
        except WhatsappTemplate.DoesNotExist:
            messages.error(request, 'قالب پیام معتبر نیست.')
            return redirect('whatsapp_api:send-whatsapp')

        message = template.content

        # اگر شماره وارد شده باشد، به آن ارسال شود
        if phone_number:
            if not (phone_number.startswith('09') and len(phone_number) == 11):
                messages.error(request, 'فرمت شماره موبایل صحیح نیست (مثال: 09123456789)')
                return redirect('whatsapp_api:send-whatsapp')

            queue_item = WhatsappQueue.objects.create(
                recipient_number=phone_number,
                template_type=template_type,
                message=message,
                status='pending'
            )
            # ارسال واقعی
            success = send_whatsapp_message(phone_number, template_type, {})
            if success:
                queue_item.status = 'sent'
                queue_item.sent_at = timezone.now()
                queue_item.save()
                WhatsappLog.objects.create(
                    recipient_number=phone_number,
                    template_type=template_type,
                    message=message,
                    status='sent',
                    sent_at=queue_item.sent_at
                )
                messages.success(request, 'پیام با موفقیت ارسال شد.')
            else:
                queue_item.status = 'failed'
                queue_item.save()
                messages.error(request, 'ارسال پیام ناموفق بود.')
            return redirect('whatsapp_api:whatsapp-dashboard')

        # اگر شماره وارد نشده بود، طبق روال قبلی به مشتری انتخابی ارسال شود
        if not customer_id:
            messages.error(request, 'لطفاً یک مشتری انتخاب کنید یا شماره موبایل وارد نمایید.')
            return redirect('whatsapp_api:send-whatsapp')

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            messages.error(request, 'مشتری انتخاب شده وجود ندارد.')
            return redirect('whatsapp_api:send-whatsapp')

        queue_item = WhatsappQueue.objects.create(
            recipient_number=customer.phone_number,
            template_type=template_type,
            message=message,
            status='pending'
        )
        # ارسال واقعی
        success = send_whatsapp_message(customer, template_type, {})
        if success:
            queue_item.status = 'sent'
            queue_item.sent_at = timezone.now()
            queue_item.save()
            WhatsappLog.objects.create(
                recipient_number=customer.phone_number,
                template_type=template_type,
                message=message,
                status='sent',
                sent_at=queue_item.sent_at
            )
            messages.success(request, 'پیام با موفقیت ارسال شد.')
        else:
            queue_item.status = 'failed'
            queue_item.save()
            messages.error(request, 'ارسال پیام ناموفق بود.')
        return redirect('whatsapp_api:whatsapp-dashboard')

    templates = WhatsappTemplate.objects.filter(is_active=True)
    customers = Customer.objects.filter(whatsapp_preference=True)

    context = {
        'templates': templates,
        'customers': customers,
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