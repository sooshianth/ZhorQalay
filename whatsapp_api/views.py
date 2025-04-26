from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import WhatsappNumber, WhatsappLog, WhatsappTemplate
from .utils import send_whatsapp_message
from core._models import Customer
import models

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
    
    return render(request, 'whatsapp_api/dashboard.html', context)

@login_required
def send_whatsapp(request):
    """ارسال پیام واتساپ جدید"""
    if request.method == 'POST':
        recipient_number = request.POST.get('recipient_number')
        template_type = request.POST.get('template_type')
        customer_id = request.POST.get('customer_id')
        
        try:
            customer = Customer.objects.get(id=customer_id) if customer_id else None
            context = {}  # می‌تونید اطلاعات اضافی برای تمپلیت اینجا اضافه کنید
            
            success = send_whatsapp_message(customer, template_type, context)
            
            if success:
                messages.success(request, 'پیام با موفقیت ارسال شد.')
            else:
                messages.error(request, 'خطا در ارسال پیام.')
                
        except Exception as e:
            messages.error(request, f'خطا: {str(e)}')
            
        return redirect('whatsapp_api:dashboard')
    
    templates = WhatsappTemplate.objects.filter(is_active=True)
    customers = Customer.objects.filter(whatsapp_consent=True)
    
    context = {
        'templates': templates,
        'customers': customers,
    }
    
    return render(request, 'whatsapp_api/send_whatsapp.html', context)

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

@login_required
def templates(request):
    """مدیریت تمپلیت‌های واتساپ"""
    templates = WhatsappTemplate.objects.all().order_by('template_type', 'name')
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'whatsapp_api/templates.html', context)